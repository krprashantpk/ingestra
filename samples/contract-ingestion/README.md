---
title: Azure Functions ingestion sample
description: Deploy HTTP and Blob triggers that store document chunks, embeddings, and metadata in Azure SQL.
---

## Overview

This sample accepts a file in either of two ways:

* `POST /api/ingest?filename=report.pdf` with the file's raw bytes and a Function key
* Upload a blob to the provisioned `documents` container

Both triggers call the shared ingestion service, which configures `Pipeline` with
`AzureContentUnderstandingConverter`, `MarkdownTokenChunker`,
`AzureOpenAIEmbeddings`, and two `AzureSQLStore` instances.
The service calls `convert(data)` for Markdown and metadata, then
`chunk(markdown)` for embedded chunks using a 2,048-token size goal and
1,536-dimensional Azure OpenAI embeddings. It persists metadata with
`ingest_metadata(metadata, metadata_mapper=...)` and chunks with
`ingest_chunks(embedded_chunks, chunk_mapper=...)`. SQL commits both storage
roles in one transaction.

The sample provisions Functions, Storage, and Azure SQL, plus the required
hosting plan and managed identity. It does not create a Foundry account,
project, model deployment, or monitoring workspace. AI services are supplied
from your existing Foundry setup.

```text
HTTP file body ----+
                   +--> Content Understanding --> chunking --> embeddings
Blob upload -------+                                             |
                                                                 v
                                                        Azure SQL transaction
                                                        |-- document_metadata
                                                        `-- document_chunks
```

### Files

| File                                                    | Purpose                                               |
|---------------------------------------------------------|-------------------------------------------------------|
| [function_app.py](function_app.py)                       | Function-key-protected HTTP and Event Grid Blob triggers |
| [services/ingestion.py](services/ingestion.py)            | Shared conversion, chunking, embedding, and ingestion  |
| [utilities/database.py](utilities/database.py)            | SQL schema and token-authenticated connections         |
| [utilities/bootstrap.py](utilities/bootstrap.py)          | SQL table setup and SQL permissions                   |
| [main.bicep](infra/main.bicep)                           | Functions, Storage, SQL, hosting plan, and identity    |
| [foundry-access.bicep](infra/foundry-access.bicep)         | Account-scoped runtime roles on existing Foundry     |
| [events.bicep](infra/events.bicep)                       | Post-publish Blob event subscription                  |
| [Deploy-Sample.ps1](Deploy-Sample.ps1)                   | Build, provision, initialize, publish, and wire events |
| [local.settings.json.example](local.settings.json.example) | Nonsecret local configuration template              |
| [tests](tests/)                                         | Offline trigger, storage, and transaction tests        |

The triggers delegate to the ingestion service. That service uses the database
utilities, and deployment runs `python -m utilities.bootstrap` to initialize the
data plane. Package initializers contain only documentation.

### File support and limits

The default `prebuilt-documentSearch` analyzer supports the document formats
listed in the [Content Understanding limits](https://learn.microsoft.com/azure/ai-services/content-understanding/service-limits#input-file-limits),
including PDF, Office documents, images, and text formats. This is not a generic
decoder for every binary format. Unsupported, encrypted, or corrupt files can
fail analysis. Audio and video require suitable analyzers and are not configured
by this document-focused sample.

* The sample limits both upload paths to 20 MiB per file.
* Only the first Content Understanding content item is retained, matching the
  library converter's contract. Do not use an analyzer that splits a file into
  multiple content items if you need all of those items.
* HTTP ingestion is synchronous. Azure's HTTP response timeout is approximately
  230 seconds even though the function timeout is 10 minutes. Use Blob uploads
  for work that might take longer.
* One document's chunks are embedded in one request. The library's 2,048-input
  limit and the model's aggregate token and rate limits still apply. This sample
  does not batch very large documents.
* Empty extraction returns HTTP 422 without changing existing SQL data.
  Provider failures return HTTP 502 with details written to the application logger.
* Blob failures are logged and raised for the Functions runtime to retry. Inspect
  `webjobs-blobtrigger-poison` after repeated processing failures. Event Grid
  separately retries event delivery for up to 24 hours.

## Provision and deploy

### Prerequisites

* Python 3.12 or newer and [uv](https://docs.astral.sh/uv/)
* PowerShell 7 or newer
* An up-to-date [Azure CLI](https://learn.microsoft.com/cli/azure/install-azure-cli)
  with Bicep available through `az bicep install`
* [Microsoft ODBC Driver 18 for SQL Server](https://learn.microsoft.com/sql/connect/odbc/download-odbc-driver-for-sql-server)
  on the deployment machine; the Python Function runtime must also provide this driver
* An interactive `az login` as a user in the target tenant, not a service-principal login
* Contributor plus permission to create role assignments, such as User Access
  Administrator, on the target resource group
* Permission to deploy the RBAC module in the existing Foundry resource group
  (`rg-agents` by default), and to create role assignments on its Foundry account
* Registered resource providers: `Microsoft.Web`, `Microsoft.Storage`,
  `Microsoft.Sql`, `Microsoft.ManagedIdentity`, and `Microsoft.EventGrid`
* A region supporting both Flex Consumption and SQL provisioning for your subscription
* When publishing code, existing Content Understanding and Azure OpenAI services,
  with their analyzers, model deployments, and permissions already configured

> [!WARNING]
> Running the deployment script creates billable resources, including an S0 SQL
> database. Calls to your existing AI services are billed separately. Public service endpoints and SQL's
> "Allow Azure services" firewall rule keep this sample small. That SQL rule
> allows network access from other Azure tenants too; SQL authentication and
> permissions still apply. Use private endpoints, network restrictions, and your
> organization's controls before using this design for sensitive data.

### Provision core infrastructure first

From the repository root, provision the Function App, Storage, and SQL without
needing AI endpoints or publishing code:

```powershell
az login
az account set --subscription '<subscription-id>'

.\samples\contract-ingestion\Deploy-Sample.ps1 `
    -ResourceGroupName 'rg-ingestra-sample' `
    -Location 'centralindia' `
    -ClientIpAddress '<your-public-ipv4>' `
    -InfrastructureOnly
```

This creates the SQL tables and grants the Function identity SQL and Foundry
runtime access, then prints the app name, SQL endpoint, and managed identity
principal ID. It does not build or publish code or connect Blob events. The
temporary SQL firewall rule is removed before the script exits.

### Existing Foundry access

[main.bicep](infra/main.bicep) defaults to the existing `mf-agents-poc` Foundry
account in `rg-agents`, in the deployment subscription. Its `proj-default`
project is not created or changed. The cross-resource-group
[access module](infra/foundry-access.bicep) grants the Function's user-assigned
managed identity these roles at the account scope:

* `Cognitive Services Content Understanding Reader`: analyze documents and read
  analysis results, without authoring analyzers or changing model defaults
* `Cognitive Services OpenAI User`: invoke the existing embedding deployment

The application calls account-level service APIs, not project management or
agent APIs, so it does not need a project administrator role. The module uses an
`existing` account declaration and creates only role assignments. Both grants
are applied even with `-InfrastructureOnly`. For another account, override the
`foundryAccountName` and `foundryResourceGroupName` Bicep parameters directly;
the PowerShell wrapper uses their defaults.

### Publish with existing AI services

The verified service endpoints for `mf-agents-poc/proj-default` are shown below.
A project URL is not itself a Content Understanding or Azure OpenAI service
endpoint. The AI resources can be in a different region from the core
infrastructure; review data residency, latency, and transfer costs.

The owner of the existing AI resources must still:

* Configure the `prebuilt-documentSearch` analyzer and its required model defaults
* Provide an embedding deployment supporting 1,536-dimensional vectors
* Allow network access from the Function App to both service endpoints

The deployment does not create or change AI accounts, projects, model
deployments, defaults, or analyzers. If model deployments have custom names,
configure Content Understanding defaults in that account and pass your embedding
deployment name explicitly:

```powershell
.\samples\contract-ingestion\Deploy-Sample.ps1 `
    -ResourceGroupName 'rg-ingestra-sample' `
    -Location 'centralindia' `
    -ClientIpAddress '<your-public-ipv4>' `
    -ContentUnderstandingEndpoint 'https://mf-agents-poc.services.ai.azure.com/' `
    -OpenAIEndpoint 'https://mf-agents-poc.openai.azure.com/' `
    -EmbeddingDeploymentName '<existing-embedding-deployment>'
```

Without `-InfrastructureOnly`, both HTTPS AI endpoints are required and checked
before any deployment changes. A valid URL alone does not establish service
compatibility or permissions. The default embedding deployment name is
`text-embedding-3-small`; the model and dimensions must match the SQL schema.

The full deployment script performs these steps:

1. Synchronize the root `.venv` using the root `samples` dependency group,
   preserving other packages already installed in that environment.
1. Deploy a Linux Python 3.12 Flex Consumption Function App, private blob
   containers, Azure SQL, the hosting plan, and a managed identity, and grant
   that identity runtime access on the existing Foundry account.
1. Use the signed-in user as SQL's Microsoft Entra administrator, temporarily
   allow your public IPv4 address, and initialize SQL tables.
1. Create a SQL user for the Function's managed identity with only
   `SELECT`, `INSERT`, `UPDATE`, and `DELETE` on the two sample tables.
1. Build this checkout into a wheel and export locked dependencies from the root
  [pyproject.toml](../../pyproject.toml), rather than downloading an unrelated
  published Ingestra package. This and the following publication steps are skipped
  with `-InfrastructureOnly`.
1. Publish a ZIP package with a Linux remote dependency build.
1. Wait for the Blob extension system key, then deploy the filtered Event Grid
   subscription. Deploying the event subscription before code publication would
   target a webhook that is not ready.
1. Verify both Functions are indexed and print the endpoint, storage account,
   and SQL database.
1. Remove the temporary SQL firewall rule and local build directory, including
   its temporary webhook parameter file, in cleanup.

No SQL password, AI API key, or storage account key is required. Managed identity
authenticates runtime SQL, AI, deployment-storage, and Blob connections.
The HTTP Function key and Blob extension system key are still runtime secrets.
The Blob webhook parameter is marked secure and is not printed by the script.

Re-running against the same resource group updates the existing sample
resources. Existing SQL data is retained. SQL initialization creates missing
tables, but is not a migration framework for future schema changes. If deployment
fails, the script stops and retains Azure resources for diagnosis; it never
deletes an existing resource group or retries a failed deployment by destroying it.
Removing resources from the template does not delete resources created by an
older version. Review the existing group before rebuilding it in a different region.
Role assignments on the external Foundry account also outlive deletion of the
sample resource group. Remove those two grants for the sample identity before
deleting the identity; do not delete the shared Foundry account or its project.

## Upload a file

Use a dedicated sample resource group so the following discovery commands select
the intended app and account:

```powershell
$ResourceGroup = 'rg-ingestra-sample'
$App = az functionapp list --resource-group $ResourceGroup --query '[0].name' --output tsv
$Hostname = az functionapp show --resource-group $ResourceGroup --name $App --query defaultHostName --output tsv
$Storage = az storage account list --resource-group $ResourceGroup --query '[0].name' --output tsv
$FunctionKey = az functionapp keys list --resource-group $ResourceGroup --name $App --query functionKeys.default --output tsv
```

### HTTP trigger

Send raw bytes, not multipart form data or base64 JSON:

```powershell
Invoke-RestMethod `
    -Uri "https://$Hostname/api/ingest?filename=report.pdf" `
    -Method Post `
    -Headers @{ 'x-functions-key' = $FunctionKey } `
    -ContentType 'application/octet-stream' `
    -InFile '.\report.pdf'
```

A successful request returns a JSON object:

```json
{
  "document_id": "a-source-derived-sha256-hex-string",
  "filename": "report.pdf",
  "chunks": 4
}
```

The key is sent in a header instead of the URL. URL-encode filenames containing
spaces, `&`, or other reserved characters.

### Blob trigger

The deployment grants the deploying user blob data access:

```powershell
az storage blob upload `
    --account-name $Storage `
    --container-name documents `
    --name 'reports/report.pdf' `
    --file '.\report.pdf' `
    --auth-mode login `
    --overwrite
```

This returns after the upload, not after ingestion. Track processing with your
configured logging destination and verify the SQL rows. Historical blobs are not scanned;
only new BlobCreated events matching this container are subscribed.

## SQL data and replacement semantics

`dbo.document_metadata` contains the stable document ID, filename, source,
content SHA-256, byte count, UTC ingestion time, and extracted field metadata.
`dbo.document_chunks` contains ordered chunk IDs, the document foreign key,
original Markdown, embedding input, a native `VECTOR(1536)` embedding, and source
page numbers.

The source key is `http:<filename>` or `blob:<container>/<blob-name>`. Its SHA-256
is the document ID. Uploading again to the same source replaces the metadata and
all chunks, including deleting obsolete chunks from an earlier, longer version.
Identical filenames uploaded over HTTP intentionally address the same document;
HTTP and Blob uploads are distinct sources even when their bytes match.
With concurrent updates, the last successful transaction wins, not necessarily
the last uploaded blob event.

Both SQL stores share one connection inside `engine.begin()`.
The service awaits `pipeline.convert(data)` and `pipeline.chunk(markdown)`
before storage. It then calls `pipeline.ingest_metadata(...)` followed by
`pipeline.ingest_chunks(...)`. The metadata upsert locks the document key until commit.
The service then deletes only obsolete chunks whose indices are beyond the new
chunk count, because the pipeline does not remove old rows. The SQL connection
is open during processing, but no SQL writes or document locks occur until
processing completes. Empty extraction raises inside the transaction, rolling
back its metadata write and preserving existing data. Processing, write, or
cleanup failures roll back the transaction. Retries are safe for SQL rows, but
AI analysis and embedding charges can repeat.

Using the deployment user's Entra identity, inspect the database with the Azure
portal query editor or a SQL client. A direct SQL client requires its public
IPv4 firewall rule because the bootstrap rule was removed.

```sql
SELECT document_id, filename, source, content_bytes, extracted_metadata
FROM dbo.document_metadata;

SELECT document_id, chunk_index, original_text, page_numbers
FROM dbo.document_chunks
ORDER BY document_id, chunk_index;
```

## Local development and offline tests

From the repository root:

```powershell
uv sync --group samples
Push-Location .\samples\contract-ingestion
try {
    uv run --project ..\.. --group samples python -m unittest discover -s tests -v
}
finally {
    Pop-Location
}

az bicep build --file .\samples\contract-ingestion\infra\main.bicep --stdout
az bicep build --file .\samples\contract-ingestion\infra\events.bicep --stdout
```

The tests mock external services and deployment commands. PowerShell control-flow
tests require `pwsh` and are skipped when it is unavailable. They do not prove live
Azure quota, networking, SQL vector support, or model access.

For local HTTP debugging, copy
[local.settings.json.example](local.settings.json.example) to the ignored
`samples\contract-ingestion\local.settings.json` and fill in the provisioned endpoints. Run Azurite
for local host storage and install Azure Functions Core Tools v4. The signed-in
user already has SQL administrator access and blob access from deployment.
AI access to your existing services must be granted separately. Add a SQL
firewall rule for your local IPv4 address while testing. The
`AZURE_OPENAI_EMBEDDING_DEPLOYMENT` setting selects your existing deployment.

```powershell
Copy-Item .\samples\contract-ingestion\local.settings.json.example .\samples\contract-ingestion\local.settings.json
$env:PATH = "$PWD\.venv\Scripts;$env:PATH"
Push-Location .\samples\contract-ingestion
try {
    func start
}
finally {
    Pop-Location
}
```

Call the local HTTP endpoint at `http://localhost:7071/api/ingest`.
The Event Grid Blob trigger needs a reachable, validated webhook, so use the
deployed Function for Blob testing; Azurite alone does not emit those events.

## Cleanup

After reviewing the resource group contents, delete a dedicated sample group
when you no longer need its data:

```powershell
az group delete --name 'rg-ingestra-sample' --yes
```
