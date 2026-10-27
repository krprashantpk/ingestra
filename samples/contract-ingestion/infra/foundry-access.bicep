metadata name = 'Existing Foundry runtime access'
metadata description = 'Grant a Function managed identity inference access without managing the Foundry account or its projects.'

@description('Name of the existing Foundry account in this resource group.')
@minLength(1)
param foundryAccountName string

@description('Object ID of the Function managed identity.')
@minLength(36)
@maxLength(36)
param principalId string

var contentUnderstandingReaderRole = subscriptionResourceId('Microsoft.Authorization/roleDefinitions', '379c52cb-64de-498c-8b5b-c6170d6c49d4')
var openAIUserRole = subscriptionResourceId('Microsoft.Authorization/roleDefinitions', '5e0bd9bd-7b93-4f28-af87-19fc36ad61bd')

resource foundryAccount 'Microsoft.CognitiveServices/accounts@2025-06-01' existing = {
  name: foundryAccountName
}

resource runtimeRoles 'Microsoft.Authorization/roleAssignments@2022-04-01' = [for role in [contentUnderstandingReaderRole, openAIUserRole]: {
  name: guid(foundryAccount.id, principalId, role)
  scope: foundryAccount
  properties: {
    principalId: principalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: role
  }
}]