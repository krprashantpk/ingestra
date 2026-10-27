"""Check core deployment, SQL bootstrap, and publication guards without Azure calls."""

import argparse
import asyncio
import re
import shutil
import subprocess
import sys
import tomllib
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, Mock, patch

from azure.core.credentials import AccessToken

from utilities import bootstrap


class DeploymentTests(unittest.TestCase):
    """Keep deployment ownership and infrastructure-only behavior explicit."""

    def _run_powershell(self, code: str) -> str:
        """Run a local validation or a deployment harness with fake external commands."""
        sample = Path(__file__).resolve().parents[1]
        result = subprocess.run(["pwsh", "-NoProfile", "-NonInteractive", "-Command", code], cwd=sample, capture_output=True, text=True, timeout=60)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        return result.stdout

    def test_given_deployment_commands_when_resolving_groups_then_uses_declared_samples_group(self) -> None:
        """Validate all script group arguments against the authoritative manifest."""
        sample = Path(__file__).resolve().parents[1]
        manifest = tomllib.loads((sample.parents[1] / "pyproject.toml").read_text(encoding="utf-8"))
        script = (sample / "Deploy-Sample.ps1").read_text(encoding="utf-8")
        groups = re.findall(r"--group\s+([\w-]+)", script)

        self.assertTrue(groups)
        self.assertEqual(set(groups), {"samples"})
        self.assertTrue(set(groups).issubset(manifest["dependency-groups"]))

    @unittest.skipUnless(shutil.which("pwsh") and shutil.which("az"), "PowerShell and Azure CLI with Bicep are required for template compilation")
    def test_given_existing_foundry_when_compiled_then_grants_only_account_inference_roles(self) -> None:
        """Compile locally and preserve external scope, identity wiring, and runtime-only roles."""
        self._run_powershell(r"""
$ErrorActionPreference = 'Stop'
$TemplateJson = & az bicep build --file ./infra/main.bicep --stdout --only-show-errors
if ($LASTEXITCODE -ne 0) { throw 'Bicep compilation failed.' }
$Template = $TemplateJson | ConvertFrom-Json
$Resources = if ($Template.resources -is [array]) { $Template.resources } else { $Template.resources.PSObject.Properties.Value }
if (@($Resources | Where-Object { $_.type -like 'Microsoft.CognitiveServices/*' }).Count) {
    throw 'The main template must not provision Foundry resources.'
}
$Modules = @($Resources | Where-Object { $_.type -eq 'Microsoft.Resources/deployments' -and $_.resourceGroup -eq "[parameters('foundryResourceGroupName')]" })
if ($Modules.Count -ne 1 -or $Modules[0].resourceGroup -ne "[parameters('foundryResourceGroupName')]") {
    throw 'Expected one access module in the existing Foundry resource group.'
}
$Module = $Modules[0]
if ($Module.properties.parameters.principalId.value -notmatch 'identity.*principalId') {
    throw 'Access must use the Function managed identity principal ID.'
}
$Nested = $Module.properties.template
$Roles = if ($Nested.resources -is [array]) { $Nested.resources } else { $Nested.resources.PSObject.Properties.Value }
if (@($Roles).Count -ne 1 -or $Roles.type -ne 'Microsoft.Authorization/roleAssignments') {
    throw 'The external module must only deploy role assignments.'
}
if ($Roles.scope -ne "[resourceId('Microsoft.CognitiveServices/accounts', parameters('foundryAccountName'))]") {
    throw 'Runtime access must be scoped to the existing Foundry account.'
}
if ($Roles.properties.principalType -ne 'ServicePrincipal' -or $Roles.properties.principalId -ne "[parameters('principalId')]") {
    throw 'Runtime roles must target the supplied managed identity.'
}
if ($Roles.properties.roleDefinitionId -ne "[createArray(variables('contentUnderstandingReaderRole'), variables('openAIUserRole'))[copyIndex()]]" -or $Roles.copy.count -ne "[length(createArray(variables('contentUnderstandingReaderRole'), variables('openAIUserRole')))]") {
    throw 'Runtime access must use exactly the two intended inference roles.'
}
foreach ($RoleId in @('379c52cb-64de-498c-8b5b-c6170d6c49d4', '5e0bd9bd-7b93-4f28-af87-19fc36ad61bd')) {
    if (-not ($Nested.variables | ConvertTo-Json -Depth 8).Contains($RoleId)) {
        throw "Required inference role missing: $RoleId"
    }
}
if ($Template.parameters.foundryAccountName.defaultValue -ne 'mf-agents-poc' -or $Template.parameters.foundryResourceGroupName.defaultValue -ne 'rg-agents') {
    throw 'The default access target must match the supplied Foundry account.'
}
""")

    @unittest.skipUnless(shutil.which("pwsh") and shutil.which("az"), "PowerShell and Azure CLI with Bicep are required for template compilation")
    def test_given_monitoring_when_compiled_then_connects_workspace_based_insights(self) -> None:
        """Provision retained telemetry and wire its connection without exposing it."""
        self._run_powershell(r"""
$ErrorActionPreference = 'Stop'
$TemplateJson = & az bicep build --file ./infra/main.bicep --stdout --only-show-errors
if ($LASTEXITCODE -ne 0) { throw 'Bicep compilation failed.' }
$Template = $TemplateJson | ConvertFrom-Json
$Resources = if ($Template.resources -is [array]) { $Template.resources } else { $Template.resources.PSObject.Properties.Value }
$Monitoring = @($Resources | Where-Object { $_.type -eq 'Microsoft.Resources/deployments' -and $_.properties.template.metadata._generator.templateHash -and $_.name -like '*monitoring*' })
if ($Monitoring.Count -ne 1) { throw 'Expected one monitoring module.' }
$Nested = $Monitoring[0].properties.template
$Telemetry = if ($Nested.resources -is [array]) { $Nested.resources } else { $Nested.resources.PSObject.Properties.Value }
$Workspace = @($Telemetry | Where-Object { $_.type -eq 'Microsoft.OperationalInsights/workspaces' })
$Insights = @($Telemetry | Where-Object { $_.type -eq 'Microsoft.Insights/components' })
if ($Workspace.Count -ne 1 -or $Workspace[0].properties.retentionInDays -ne 30) { throw 'Expected a 30-day Log Analytics workspace.' }
if ($Insights.Count -ne 1 -or -not $Insights[0].properties.WorkspaceResourceId) { throw 'Application Insights must be workspace based.' }
if ($Nested.outputs.connectionString.type -ne 'secureString') { throw 'The monitoring connection string output must be protected.' }
$App = @($Resources | Where-Object { $_.type -eq 'Microsoft.Web/sites' })[0]
$Settings = $App.properties.siteConfig.appSettings | ConvertTo-Json -Depth 20
if (-not $Settings.Contains('APPLICATIONINSIGHTS_CONNECTION_STRING') -or $Settings -notmatch 'monitoring.*connectionString') { throw 'The Functions host must use the monitoring connection string.' }
""")

    @unittest.skipUnless(shutil.which("pwsh"), "PowerShell is required for deployment control-flow tests")
    def test_given_infrastructure_only_when_deployed_then_bootstraps_sql_without_publishing(self) -> None:
        """Stop before building or publishing code and still remove the temporary SQL rule."""
        output = self._run_powershell(r"""
$ErrorActionPreference = 'Stop'
$global:AzureCalls = [System.Collections.Generic.List[string]]::new()
$global:UvCalls = [System.Collections.Generic.List[string]]::new()
function az {
    $Command = $args -join ' '
    $global:AzureCalls.Add($Command)
    $global:LASTEXITCODE = 0
    if ($Command.StartsWith('ad signed-in-user show')) {
        return '{"id":"5596fe0a-f12d-45e9-9273-f252ddfa7066","userPrincipalName":"test@example.com"}'
    }
    if ($Command.StartsWith('deployment group create')) {
        return (@{ properties = @{ outputs = @{ deployment = @{ value = @{
            functionAppName = 'func-test'
            sqlServerName = 'sql-test'
            sqlServer = 'sql-test.database.windows.net'
            databaseName = 'ingestra'
            clientId = '48713c72-4ceb-4ecc-97f5-811559f5de45'
            principalId = '5596fe0a-f12d-45e9-9273-f252ddfa7066'
        } } } } } | ConvertTo-Json -Depth 8)
    }
}
function uv {
    $global:UvCalls.Add(($args -join ' '))
    $global:LASTEXITCODE = 0
}
& ./Deploy-Sample.ps1 -ResourceGroupName rg-test -Location centralindia -ClientIpAddress 203.0.113.10 -InfrastructureOnly
if (@($global:UvCalls | Where-Object { $_ -match 'python -m utilities.bootstrap --sql-server' }).Count -ne 1) {
    throw 'SQL bootstrap was not invoked.'
}
if (@($global:UvCalls | Where-Object { $_ -match '--client-id 48713c72-4ceb-4ecc-97f5-811559f5de45' }).Count -ne 1) {
    throw 'SQL bootstrap must use the managed identity client ID, not its object ID.'
}
if (@($global:UvCalls | Where-Object { $_ -match '--ai-endpoint|^build |^export ' }).Count) {
    throw 'Infrastructure-only deployment invoked AI bootstrap or package building.'
}
if (@($global:AzureCalls | Where-Object { $_ -match '^functionapp ' }).Count) {
    throw 'Infrastructure-only deployment attempted to publish code.'
}
if (@($global:AzureCalls | Where-Object { $_ -match '^deployment group create' }).Count -ne 1) {
    throw 'Infrastructure-only deployment attempted to configure Blob events.'
}
if (@($global:AzureCalls | Where-Object { $_ -match '^sql server firewall-rule delete' }).Count -ne 1) {
    throw 'The temporary SQL firewall rule was not removed.'
}
""")

        self.assertIn("Core infrastructure and SQL are ready", output)
        self.assertIn("Code and Blob events were not published", output)

    @unittest.skipUnless(shutil.which("pwsh"), "PowerShell is required for deployment control-flow tests")
    def test_given_missing_ai_endpoints_when_publishing_then_rejects_before_external_calls(self) -> None:
        """Require existing AI configuration before any full-deployment side effects."""
        self._run_powershell(r"""
$ErrorActionPreference = 'Stop'
function az { throw 'Azure must not be called before endpoint validation.' }
function uv { throw 'uv must not be called before endpoint validation.' }
try {
    & ./Deploy-Sample.ps1 -ResourceGroupName rg-test -Location centralindia -ClientIpAddress 203.0.113.10
    throw 'Missing AI endpoints were accepted.'
}
catch {
    if ($_.Exception.Message -notlike 'ContentUnderstandingEndpoint must be an existing HTTPS service endpoint*') {
        throw
    }
}
Write-Output 'Endpoint validation: PASS'
""")

    def test_given_sql_bootstrap_when_help_requested_then_requires_no_ai_configuration(self) -> None:
        """Expose SQL-only CLI parameters without an AI endpoint or model-default setup."""
        sample = Path(__file__).resolve().parents[1]
        result = subprocess.run([sys.executable, "-m", "utilities.bootstrap", "--help"], cwd=sample, capture_output=True, text=True, timeout=60)

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("--sql-server", result.stdout)
        self.assertIn("--client-id", result.stdout)
        self.assertNotIn("--principal-id", result.stdout)
        self.assertNotIn("--ai-endpoint", result.stdout)

    def test_given_managed_identity_client_id_when_bootstrapped_then_uses_application_sid(self) -> None:
        """Map service-principal tokens through their client ID rather than object ID."""
        args = argparse.Namespace(sql_server="test.database.windows.net", database="ingestra", client_id="48713c72-4ceb-4ecc-97f5-811559f5de45")
        connection = Mock()
        connection.run_sync = AsyncMock()
        connection.execute = AsyncMock()
        with patch("utilities.bootstrap.AzureCliCredential") as credential_factory, patch("utilities.bootstrap.create_sql_engine") as engine_factory:
            credential_factory.return_value.__aenter__.return_value.get_token = AsyncMock(return_value=AccessToken("token", 9999999999))
            engine = engine_factory.return_value
            engine.begin.return_value.__aenter__.return_value = connection
            engine.dispose = AsyncMock()

            asyncio.run(bootstrap.initialize(args))

        statement = str(connection.execute.await_args.args[0])
        self.assertIn("SID = 0x723c7148eb4ccc4e97f5811559f5de45, TYPE = E", statement)
        self.assertNotIn("c35f18051ba75e41a53c7212d3450c7e", statement)
        engine.dispose.assert_awaited_once()


if __name__ == "__main__":
    unittest.main()
