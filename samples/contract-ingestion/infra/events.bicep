metadata name = 'Ingestra blob event subscription'
metadata description = 'Wire new blobs to the published event-based Blob trigger.'

@description('Region of the source storage account.')
param location string = resourceGroup().location

@description('Source storage account name.')
param storageAccountName string

@description('Container monitored by the Blob trigger.')
param containerName string = 'documents'

@secure()
@description('Published Blob extension webhook URL, including its system key.')
param webhookEndpoint string

resource storage 'Microsoft.Storage/storageAccounts@2023-05-01' existing = {
  name: storageAccountName
}

resource topic 'Microsoft.EventGrid/systemTopics@2022-06-15' = {
  name: 'evgt-ingestra-${uniqueString(storage.id)}'
  location: location
  properties: {
    source: storage.id
    topicType: 'Microsoft.Storage.StorageAccounts'
  }
}

resource subscription 'Microsoft.EventGrid/systemTopics/eventSubscriptions@2022-06-15' = {
  parent: topic
  name: 'ingest-blob-created'
  properties: {
    destination: {
      endpointType: 'WebHook'
      properties: { endpointUrl: webhookEndpoint }
    }
    eventDeliverySchema: 'EventGridSchema'
    filter: {
      includedEventTypes: ['Microsoft.Storage.BlobCreated']
      subjectBeginsWith: '/blobServices/default/containers/${containerName}/blobs/'
      isSubjectCaseSensitive: true
    }
    retryPolicy: {
      maxDeliveryAttempts: 30
      eventTimeToLiveInMinutes: 1440
    }
  }
}
