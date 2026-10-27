metadata name = 'Ingestra Functions sample'
metadata description = 'Deploy keyless Functions, Storage, and Azure SQL using caller-owned AI services.'

@description('Region for Functions, Storage, and SQL. Must support Flex Consumption.')
param location string = resourceGroup().location

@description('Existing Content Understanding service endpoint. Omit for infrastructure-only deployment.')
param contentUnderstandingEndpoint string?

@description('Existing Azure OpenAI service endpoint. Omit for infrastructure-only deployment.')
param openAIEndpoint string?

@description('Existing Azure OpenAI embedding deployment name. Must provide 1536-dimensional embeddings.')
param embeddingDeploymentName string = 'text-embedding-3-small'

@description('Existing Foundry account used for Content Understanding and embeddings. The account is not created or modified.')
@minLength(1)
param foundryAccountName string = 'mf-agents-poc'

@description('Resource group containing the existing Foundry account, in the current subscription.')
@minLength(1)
param foundryResourceGroupName string = 'rg-agents'

@description('Object ID of the signed-in deployment user, configured as SQL Entra administrator.')
param sqlAdminObjectId string

@description('User principal name of the signed-in deployment user.')
param sqlAdminLogin string

@description('Database name.')
param databaseName string = 'ingestra'

@description('Blob container monitored by the ingestion trigger.')
param containerName string = 'documents'

var suffix = uniqueString(resourceGroup().id)
var storageName = 'sting${suffix}'
var appName = 'func-ingestra-${suffix}'
var blobOwnerRole = subscriptionResourceId('Microsoft.Authorization/roleDefinitions', 'b7e6dc6d-f1e8-4753-8033-0f276bb0955b')
var queueRole = subscriptionResourceId('Microsoft.Authorization/roleDefinitions', '974c5e8b-45b9-4653-ba55-5f855dd0fb88')
var storageRole = subscriptionResourceId('Microsoft.Authorization/roleDefinitions', '17d1049b-9a84-46fb-8f53-869881c3d3ab')

module monitoring './monitoring.bicep' = {
  name: 'monitoring-${suffix}'
  params: {
    location: location
  }
}

resource identity 'Microsoft.ManagedIdentity/userAssignedIdentities@2023-01-31' = {
  name: 'id-ingestra-${suffix}'
  location: location
}

module foundryAccess './foundry-access.bicep' = {
  name: 'foundry-access-${suffix}'
  scope: resourceGroup(foundryResourceGroupName)
  params: {
    foundryAccountName: foundryAccountName
    principalId: identity.properties.principalId
  }
}

resource storage 'Microsoft.Storage/storageAccounts@2023-05-01' = {
  name: storageName
  location: location
  kind: 'StorageV2'
  sku: { name: 'Standard_LRS' }
  properties: {
    accessTier: 'Hot'
    allowBlobPublicAccess: false
    allowSharedKeyAccess: false
    minimumTlsVersion: 'TLS1_2'
    supportsHttpsTrafficOnly: true
  }
}

resource blobService 'Microsoft.Storage/storageAccounts/blobServices@2023-05-01' = {
  parent: storage
  name: 'default'
}

resource inputContainer 'Microsoft.Storage/storageAccounts/blobServices/containers@2023-05-01' = {
  parent: blobService
  name: containerName
  properties: { publicAccess: 'None' }
}

resource deploymentContainer 'Microsoft.Storage/storageAccounts/blobServices/containers@2023-05-01' = {
  parent: blobService
  name: 'deployments'
  properties: { publicAccess: 'None' }
}

resource storageRoles 'Microsoft.Authorization/roleAssignments@2022-04-01' = [for role in [blobOwnerRole, queueRole, storageRole]: {
  name: guid(storage.id, identity.id, role)
  scope: storage
  properties: {
    principalId: identity.properties.principalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: role
  }
}]

resource deployerBlobRole 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(storage.id, sqlAdminObjectId, blobOwnerRole)
  scope: storage
  properties: {
    principalId: sqlAdminObjectId
    principalType: 'User'
    roleDefinitionId: blobOwnerRole
  }
}

resource sql 'Microsoft.Sql/servers@2023-08-01' = {
  name: 'sql-ingestra-${suffix}'
  location: location
  properties: {
    version: '12.0'
    minimalTlsVersion: '1.2'
    publicNetworkAccess: 'Enabled'
    administrators: {
      administratorType: 'ActiveDirectory'
      azureADOnlyAuthentication: true
      login: sqlAdminLogin
      sid: sqlAdminObjectId
      tenantId: tenant().tenantId
      principalType: 'User'
    }
  }
}

// Sample-only public networking; production deployments should use private endpoints.
resource azureSqlAccess 'Microsoft.Sql/servers/firewallRules@2023-08-01' = {
  parent: sql
  name: 'AllowAzureServices'
  properties: {
    startIpAddress: '0.0.0.0'
    endIpAddress: '0.0.0.0'
  }
}

resource database 'Microsoft.Sql/servers/databases@2023-08-01' = {
  parent: sql
  name: databaseName
  location: location
  sku: {
    name: 'S0'
    tier: 'Standard'
  }
  properties: {
    maxSizeBytes: 2147483648
    requestedBackupStorageRedundancy: 'Local'
  }
}

resource plan 'Microsoft.Web/serverfarms@2024-04-01' = {
  name: 'plan-ingestra-${suffix}'
  location: location
  kind: 'functionapp'
  sku: { name: 'FC1', tier: 'FlexConsumption' }
  properties: { reserved: true }
}

resource app 'Microsoft.Web/sites@2024-04-01' = {
  name: appName
  location: location
  kind: 'functionapp,linux'
  identity: {
    type: 'UserAssigned'
    userAssignedIdentities: { '${identity.id}': {} }
  }
  properties: {
    serverFarmId: plan.id
    httpsOnly: true
    functionAppConfig: {
      runtime: { name: 'python', version: '3.12' }
      deployment: {
        storage: {
          type: 'blobContainer'
          value: '${storage.properties.primaryEndpoints.blob}${deploymentContainer.name}'
          authentication: {
            type: 'UserAssignedIdentity'
            userAssignedIdentityResourceId: identity.id
          }
        }
      }
      scaleAndConcurrency: {
        instanceMemoryMB: 2048
        maximumInstanceCount: 40
        triggers: { http: { perInstanceConcurrency: 1 } }
      }
    }
    siteConfig: {
      minTlsVersion: '1.2'
      scmMinTlsVersion: '1.2'
      ftpsState: 'Disabled'
      appSettings: [
        { name: 'APPLICATIONINSIGHTS_CONNECTION_STRING', value: monitoring.outputs.connectionString }
        { name: 'AZURE_CLIENT_ID', value: identity.properties.clientId }
        { name: 'AzureWebJobsStorage__credential', value: 'managedidentity' }
        { name: 'AzureWebJobsStorage__clientId', value: identity.properties.clientId }
        { name: 'AzureWebJobsStorage__blobServiceUri', value: storage.properties.primaryEndpoints.blob }
        { name: 'AzureWebJobsStorage__queueServiceUri', value: storage.properties.primaryEndpoints.queue }
        { name: 'AzureWebJobsStorage__tableServiceUri', value: storage.properties.primaryEndpoints.table }
        { name: 'IngestStorage__credential', value: 'managedidentity' }
        { name: 'IngestStorage__clientId', value: identity.properties.clientId }
        { name: 'IngestStorage__blobServiceUri', value: storage.properties.primaryEndpoints.blob }
        { name: 'IngestStorage__queueServiceUri', value: storage.properties.primaryEndpoints.queue }
        { name: 'INGEST_CONTAINER', value: inputContainer.name }
        ...(!empty(contentUnderstandingEndpoint) ? [{ name: 'AZURE_CONTENT_UNDERSTANDING_ENDPOINT', value: contentUnderstandingEndpoint! }] : [])
        { name: 'AZURE_CONTENT_UNDERSTANDING_ANALYZER', value: 'prebuilt-documentSearch' }
        ...(!empty(openAIEndpoint) ? [{ name: 'AZURE_OPENAI_ENDPOINT', value: openAIEndpoint! }] : [])
        { name: 'AZURE_OPENAI_EMBEDDING_DEPLOYMENT', value: embeddingDeploymentName }
        { name: 'AZURE_SQL_SERVER', value: sql.properties.fullyQualifiedDomainName }
        { name: 'AZURE_SQL_DATABASE', value: database.name }
      ]
    }
  }
  dependsOn: [storageRoles, foundryAccess]
}

@description('Names and endpoints consumed by the deployment script. Contains no secrets.')
output deployment object = {
  functionAppName: app.name
  functionHostname: app.properties.defaultHostName
  storageAccountName: storage.name
  containerName: inputContainer.name
  sqlServerName: sql.name
  sqlServer: sql.properties.fullyQualifiedDomainName
  databaseName: database.name
  clientId: identity.properties.clientId
  principalId: identity.properties.principalId
  applicationInsightsName: monitoring.outputs.applicationInsightsName
  logAnalyticsWorkspaceId: monitoring.outputs.workspaceResourceId
}
