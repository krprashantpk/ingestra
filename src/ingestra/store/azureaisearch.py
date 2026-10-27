"""Reusable asynchronous storage in one caller-defined Azure AI Search index."""

import logging

from azure.search.documents.aio import SearchClient
from azure.search.documents.indexes.models import SearchIndex

from .markdown.base import BaseMarkdownStore
from .metadata.base import BaseMetadataStore

logger = logging.getLogger(__name__)


class AzureAISearchStore(BaseMarkdownStore, BaseMetadataStore):
    """Upload either Markdown chunks or metadata to one existing search index.

    Schemas and mappers define all field names and identifiers. Index provisioning
    and document validation belong to the caller, who also owns the supplied
    document client. Configure one client and schema per role's target index.
    The supplied client's authentication, transport, retries, and timeouts are
    preserved. The store never enters or closes the client.
    """

    def __init__(self, client: SearchClient, index: SearchIndex) -> None:
        """Keep the caller's client and target schema without making requests.

        Args:
            client: Caller-owned asynchronous document client configured for the target index.
            index: Existing schema matching the client's index for mapped chunks or metadata.

        Raises:
            TypeError: The client is not an asynchronous SearchClient.
            ValueError: The index has no key field.
        """
        if not isinstance(client, SearchClient):
            raise TypeError("client must be an asynchronous SearchClient configured for the target index")
        self._client = client
        self._index = index
        self._key = self._key_field(index)

    @staticmethod
    def _key_field(index: SearchIndex) -> str:
        """Find the schema key used to correlate indexing responses.

        Args:
            index: Caller-supplied index schema.

        Returns:
            The schema-defined key field name.

        Raises:
            ValueError: The index has no key field.
        """
        for field in index.fields:
            if field.key:
                return field.name
        raise ValueError(f"Index {index.name!r} must define a key field")

    async def _store_documents(self, documents: list[dict[str, object]]) -> None:
        """Upload bounded batches and require a successful result for each key.

        Args:
            documents: Mapped documents to upsert.

        Raises:
            ValueError: A document key is missing, empty, not a string, or duplicated.
            RuntimeError: A result fails, is missing, or references an unexpected key.
        """
        keys: set[str] = set()
        for document in documents:
            key = document.get(self._key)
            if not isinstance(key, str) or not key:
                raise ValueError(f"Each document must have a nonempty string key in {self._key!r}")
            if key in keys:
                raise ValueError(f"Duplicate document key {key!r} in index {self._index.name!r}")
            keys.add(key)

        logger.info("Storing %d documents in index '%s'", len(documents), self._index.name)
        for offset in range(0, len(documents), 1000):
            batch = documents[offset : offset + 1000]
            expected_keys = {document[self._key] for document in batch}
            results = await self._client.upload_documents(documents=batch)
            for result in results:
                if not result.succeeded:
                    raise RuntimeError(f"Azure AI Search indexing failed in {self._index.name!r} for {result.key!r} (status {result.status_code}): {result.error_message}")
            if len(results) != len(batch) or {result.key for result in results} != expected_keys:
                raise RuntimeError(f"Azure AI Search indexing results in {self._index.name!r} do not match the uploaded keys")
        logger.info("Stored %d documents in index '%s'", len(documents), self._index.name)
