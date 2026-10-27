metadata name = 'Ingestra sample monitoring'
metadata description = 'Workspace-based Application Insights for ingestion requests, traces, and exceptions.'

@description('Region for Application Insights and Log Analytics.')
param location string = resourceGroup().location

var suffix = uniqueString(resourceGroup().id)

resource workspace 'Microsoft.OperationalInsights/workspaces@2023-09-01' = {
  name: 'log-ingestra-${suffix}'
  location: location
  properties: {
    retentionInDays: 30
    sku: { name: 'PerGB2018' }
  }
}

resource insights 'Microsoft.Insights/components@2020-02-02' = {
  name: 'appi-ingestra-${suffix}'
  location: location
  kind: 'web'
  properties: {
    Application_Type: 'web'
    WorkspaceResourceId: workspace.id
  }
}

@description('Application Insights connection string consumed by the Functions host.')
@secure()
output connectionString string = insights.properties.ConnectionString

@description('Application Insights component name.')
output applicationInsightsName string = insights.name

@description('Application Insights resource ID.')
output applicationInsightsResourceId string = insights.id

@description('Log Analytics workspace resource ID.')
output workspaceResourceId string = workspace.id