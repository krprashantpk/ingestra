#!/usr/bin/env pwsh
# Copyright (c) Microsoft Corporation.
# SPDX-License-Identifier: MIT
#Requires -Version 7.0

<#
.SYNOPSIS
    Provision core infrastructure and optionally publish the Ingestra Functions sample.
.DESCRIPTION
    Deploy Functions, Storage, and SQL, initialize SQL, then optionally build
    and publish a Function package using existing AI services and connect Blob events.
.PARAMETER ResourceGroupName
    Resource group to create or reuse.
.PARAMETER Location
    Region supporting Flex Consumption.
.PARAMETER ClientIpAddress
    Public IPv4 address of this machine, temporarily allowed for SQL setup.
.PARAMETER ContentUnderstandingEndpoint
    Existing Content Understanding service endpoint, required when publishing code.
.PARAMETER OpenAIEndpoint
    Existing Azure OpenAI service endpoint, required when publishing code.
.PARAMETER EmbeddingDeploymentName
    Existing embedding deployment that supports 1536-dimensional vectors.
.PARAMETER InfrastructureOnly
    Provision core resources and initialize SQL without publishing code or connecting Blob events.
.EXAMPLE
    .\samples\contract-ingestion\Deploy-Sample.ps1 -ResourceGroupName rg-ingestra -Location centralindia -ClientIpAddress 203.0.113.10 -InfrastructureOnly
.NOTES
    Requires PowerShell 7, Azure CLI, uv, ODBC Driver 18, and an interactive az login.
    Creates billable resources. Does not delete partially provisioned Azure resources.
#>

[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [ValidateNotNullOrEmpty()]
    [string]$ResourceGroupName,

    [Parameter(Mandatory = $true)]
    [ValidateNotNullOrEmpty()]
    [string]$Location,

    [Parameter(Mandatory = $true)]
    [System.Net.IPAddress]$ClientIpAddress,

    [Parameter(Mandatory = $false)]
    [string]$ContentUnderstandingEndpoint,

    [Parameter(Mandatory = $false)]
    [string]$OpenAIEndpoint,

    [Parameter(Mandatory = $false)]
    [ValidateNotNullOrEmpty()]
    [string]$EmbeddingDeploymentName = 'text-embedding-3-small',

    [Parameter(Mandatory = $false)]
    [switch]$InfrastructureOnly
)

$ErrorActionPreference = 'Stop'

#region Functions

function Invoke-AzureCli {
    <#
    .SYNOPSIS
        Run Azure CLI and stop on any nonzero exit code.
    .PARAMETER Arguments
        Azure CLI argument list.
    .OUTPUTS
        Azure CLI standard output.
    #>
    [CmdletBinding()]
    [OutputType([string[]])]
    param([Parameter(Mandatory = $true)][string[]]$Arguments)

    $Output = & az @Arguments --only-show-errors
    if ($LASTEXITCODE -ne 0) {
        throw "Azure CLI operation '$($Arguments[0..1] -join ' ')' failed with exit code $LASTEXITCODE."
    }
    return $Output
}

#endregion Functions

#region Main Execution

if ($MyInvocation.InvocationName -ne '.') {
    $Stage = $null
    $FirewallCreated = $false
    $Outputs = $null
    $RunId = [guid]::NewGuid().ToString('N')
    $FirewallRule = "sample-bootstrap-$RunId"
    try {
        if ($ClientIpAddress.AddressFamily -ne [System.Net.Sockets.AddressFamily]::InterNetwork) {
            throw 'ClientIpAddress must be the public IPv4 address used to connect to Azure SQL.'
        }
        foreach ($EndpointName in @('ContentUnderstandingEndpoint', 'OpenAIEndpoint')) {
            $EndpointValue = Get-Variable -Name $EndpointName -ValueOnly
            if (-not $EndpointValue -and $InfrastructureOnly) { continue }
            $EndpointUri = $null
            if (-not [uri]::TryCreate($EndpointValue, [System.UriKind]::Absolute, [ref]$EndpointUri) -or $EndpointUri.Scheme -ne 'https') {
                throw "$EndpointName must be an existing HTTPS service endpoint when publishing code. Use -InfrastructureOnly to provision resources without AI configuration."
            }
        }
        foreach ($Tool in @('az', 'uv')) {
            if (-not (Get-Command $Tool -ErrorAction SilentlyContinue)) {
                throw "Required tool '$Tool' was not found."
            }
        }
        $RepoRoot = Split-Path (Split-Path $PSScriptRoot -Parent) -Parent
        $User = Invoke-AzureCli -Arguments @('ad', 'signed-in-user', 'show', '--output', 'json') | ConvertFrom-Json
        Invoke-AzureCli -Arguments @('account', 'show', '--output', 'none')
        & uv sync --project $RepoRoot --group samples --inexact
        if ($LASTEXITCODE -ne 0) { throw 'Dependency synchronization failed.' }
        & uv run --project $RepoRoot --group samples python -c "import pyodbc; assert 'ODBC Driver 18 for SQL Server' in pyodbc.drivers(), 'Install Microsoft ODBC Driver 18 for SQL Server before deploying.'"
        if ($LASTEXITCODE -ne 0) { throw 'The SQL driver prerequisite check failed.' }

        $Stage = Join-Path $PSScriptRoot ".build-$RunId"
        New-Item -ItemType Directory -Path $Stage -Force | Out-Null

        Write-Host 'Deploying Functions, Storage, and SQL infrastructure...'
        Invoke-AzureCli -Arguments @('group', 'create', '--name', $ResourceGroupName, '--location', $Location, '--output', 'none')
        $Parameters = @{
            location = @{ value = $Location }
            sqlAdminObjectId = @{ value = $User.id }
            sqlAdminLogin = @{ value = $User.userPrincipalName }
            embeddingDeploymentName = @{ value = $EmbeddingDeploymentName }
        }
        if ($ContentUnderstandingEndpoint) { $Parameters.contentUnderstandingEndpoint = @{ value = $ContentUnderstandingEndpoint } }
        if ($OpenAIEndpoint) { $Parameters.openAIEndpoint = @{ value = $OpenAIEndpoint } }
        $ParameterFile = Join-Path $Stage 'infra.parameters.json'
        @{ parameters = $Parameters } | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $ParameterFile -Encoding utf8
        $Deployment = Invoke-AzureCli -Arguments @('deployment', 'group', 'create', '--resource-group', $ResourceGroupName, '--name', "ingestra-$RunId", '--template-file', (Join-Path $PSScriptRoot 'infra\main.bicep'), '--parameters', "@$ParameterFile", '--output', 'json') | ConvertFrom-Json
        $Outputs = $Deployment.properties.outputs.deployment.value

        Write-Host 'Initializing SQL schema and SQL permissions...'
        Invoke-AzureCli -Arguments @('sql', 'server', 'firewall-rule', 'create', '--resource-group', $ResourceGroupName, '--server', $Outputs.sqlServerName, '--name', $FirewallRule, '--start-ip-address', $ClientIpAddress.ToString(), '--end-ip-address', $ClientIpAddress.ToString(), '--output', 'none')
        $FirewallCreated = $true
        Push-Location $PSScriptRoot
        try {
            & uv run --project $RepoRoot --group samples python -m utilities.bootstrap --sql-server $Outputs.sqlServer --database $Outputs.databaseName --client-id $Outputs.clientId
            if ($LASTEXITCODE -ne 0) { throw 'SQL initialization failed.' }
        }
        finally {
            Pop-Location
        }

        if ($InfrastructureOnly) {
            Write-Host "Core infrastructure and SQL are ready. Function App: $($Outputs.functionAppName)"
            Write-Host "SQL: $($Outputs.sqlServer)/$($Outputs.databaseName)"
            Write-Host "Function managed identity principal ID: $($Outputs.principalId)"
            Write-Host 'Code and Blob events were not published. Configure existing AI access before publishing.'
            return
        }

        $Package = Join-Path $Stage 'app'
        New-Item -ItemType Directory -Path $Package -Force | Out-Null
        Copy-Item -LiteralPath (Join-Path $PSScriptRoot 'function_app.py'), (Join-Path $PSScriptRoot 'host.json') -Destination $Package
        foreach ($Directory in @('services', 'utilities')) {
            Copy-Item -LiteralPath (Join-Path $PSScriptRoot $Directory) -Destination $Package -Recurse
        }
        $Wheels = Join-Path $Package 'wheels'
        & uv build --project $RepoRoot --wheel --out-dir $Wheels
        if ($LASTEXITCODE -ne 0) { throw 'Building the Ingestra wheel failed.' }
        $Requirements = Join-Path $Package 'requirements.txt'
        & uv export --project $RepoRoot --locked --group samples --no-dev --no-emit-project --no-hashes --no-header --output-file $Requirements > $null
        if ($LASTEXITCODE -ne 0) { throw 'Exporting deployment requirements failed.' }
        $BuiltWheels = @(Get-ChildItem -LiteralPath $Wheels -Filter '*.whl')
        if ($BuiltWheels.Count -ne 1) { throw 'Expected exactly one Ingestra wheel.' }
        $Wheel = $BuiltWheels[0]
        Add-Content -LiteralPath $Requirements -Value "./wheels/$($Wheel.Name)" -Encoding utf8
        $ZipPath = Join-Path $Stage 'function.zip'
        Compress-Archive -Path (Join-Path $Package '*') -DestinationPath $ZipPath

        Write-Host 'Publishing Function code with a Linux remote build...'
        Invoke-AzureCli -Arguments @('functionapp', 'deployment', 'source', 'config-zip', '--resource-group', $ResourceGroupName, '--name', $Outputs.functionAppName, '--src', $ZipPath, '--build-remote', 'true', '--timeout', '1800', '--output', 'none')
        $BlobKey = $null
        for ($Attempt = 0; $Attempt -lt 18; $Attempt++) {
            $BlobKey = & az functionapp keys list --resource-group $ResourceGroupName --name $Outputs.functionAppName --query systemKeys.blobs_extension --output tsv --only-show-errors
            if ($LASTEXITCODE -eq 0 -and $BlobKey) { break }
            $BlobKey = $null
            Write-Warning "Waiting for the Function Blob extension to become ready (attempt $($Attempt + 1) of 18)."
            Start-Sleep -Seconds 10
        }
        if (-not $BlobKey) { throw 'The Blob extension key was not ready; inspect Function startup logs.' }
        $EventParameters = @{
            location = @{ value = $Location }
            storageAccountName = @{ value = $Outputs.storageAccountName }
            containerName = @{ value = $Outputs.containerName }
            webhookEndpoint = @{ value = "https://$($Outputs.functionHostname)/runtime/webhooks/blobs?functionName=Host.Functions.IngestBlob&code=$([uri]::EscapeDataString($BlobKey))" }
        }
        $EventParameterFile = Join-Path $Stage 'events.parameters.json'
        @{ parameters = $EventParameters } | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $EventParameterFile -Encoding utf8
        Invoke-AzureCli -Arguments @('deployment', 'group', 'create', '--resource-group', $ResourceGroupName, '--name', "events-$RunId", '--template-file', (Join-Path $PSScriptRoot 'infra\events.bicep'), '--parameters', "@$EventParameterFile", '--output', 'none')

        $Functions = Invoke-AzureCli -Arguments @('functionapp', 'function', 'list', '--resource-group', $ResourceGroupName, '--name', $Outputs.functionAppName, '--output', 'json') | ConvertFrom-Json
        foreach ($FunctionName in @('IngestHttp', 'IngestBlob')) {
            if (-not ($Functions | Where-Object { ($_.name -split '/')[-1] -eq $FunctionName })) {
                throw "Published Function '$FunctionName' was not indexed."
            }
        }
        Write-Host "Deployed both triggers. HTTP endpoint: https://$($Outputs.functionHostname)/api/ingest"
        Write-Host "Blob uploads: $($Outputs.storageAccountName)/$($Outputs.containerName)"
        Write-Host "SQL: $($Outputs.sqlServer)/$($Outputs.databaseName)"
    }
    catch {
        Write-Error -ErrorAction Continue "Sample deployment failed: $($_.Exception.Message)"
        throw
    }
    finally {
        try {
            if ($FirewallCreated) {
                Invoke-AzureCli -Arguments @('sql', 'server', 'firewall-rule', 'delete', '--resource-group', $ResourceGroupName, '--server', $Outputs.sqlServerName, '--name', $FirewallRule, '--output', 'none')
            }
        }
        finally {
            if ($Stage -and (Test-Path -LiteralPath $Stage)) {
                Remove-Item -LiteralPath $Stage -Recurse -Force
            }
        }
    }
}

#endregion Main Execution
