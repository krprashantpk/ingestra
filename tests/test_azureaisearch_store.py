"""Tests for single-target Azure AI Search storage without service requests."""

import json
import unittest
from itertools import count
from unittest.mock import AsyncMock, MagicMock, Mock

from azure.core.credentials import AzureKeyCredential
from azure.core.exceptions import HttpResponseError
from azure.core.pipeline.transport import AsyncHttpResponse, AsyncHttpTransport, HttpRequest
from azure.search.documents.aio import SearchClient
from azure.search.documents.indexes.models import SearchIndex, SimpleField
from azure.search.documents.models import IndexingResult

from ingestra.pipeline import EmbeddedChunk
from ingestra.store import AzureAISearchStore, BaseMarkdownStore, BaseMetadataStore


def success(documents: list[dict[str, object]]) -> list[IndexingResult]:
    """Build successful responses using the caller-defined key field."""
    return [IndexingResult.deserialize({"key": document["key"], "status": True, "statusCode": 201}) for document in documents]


class AzureAISearchStoreTests(unittest.IsolatedAsyncioTestCase):
    """Verify both roles reuse a single-index implementation."""

    def setUp(self) -> None:
        """Create caller-owned clients, one target schema, and a source chunk."""
        self.client = MagicMock(spec=SearchClient)
        self.client.upload_documents = AsyncMock(side_effect=success)
        self.index = SearchIndex(name="chunks", fields=[SimpleField(name="key", type="Edm.String", key=True)])
        self.chunk = EmbeddedChunk("# Source", "Source", [1.0, 2.0])
        self.store = AzureAISearchStore(self.client, self.index)

    def test_construction_is_request_free_and_supports_both_roles(self) -> None:
        """Require no index provisioning or network access during construction."""
        self.assertIsInstance(self.store, BaseMarkdownStore)
        self.assertIsInstance(self.store, BaseMetadataStore)
        self.assertEqual(self.client.method_calls, [])
        with self.assertRaisesRegex(ValueError, "key field"):
            AzureAISearchStore(self.client, SearchIndex(name="missing", fields=[]))

    def test_given_administration_client_when_constructing_then_reports_required_client_type(self) -> None:
        """Reject the old administration-client contract before any uploads."""
        with self.assertRaisesRegex(TypeError, "SearchClient"):
            AzureAISearchStore(Mock(), self.index)

    async def test_uploads_complete_chunk_documents_without_adding_fields(self) -> None:
        """Respect arbitrary mapped field names and retain supplied embeddings."""
        document: dict[str, object] = {"key": "one", "source": self.chunk.original_text, "input": self.chunk.embedding_text, "vector": self.chunk.embedding}
        result = await self.store.store_markdown([self.chunk], chunk_mapper=lambda chunk: document)
        self.assertIsNone(result)
        self.client.upload_documents.assert_awaited_once_with(documents=[document])
        self.client.__aenter__.assert_not_called()
        self.client.__aexit__.assert_not_called()
        self.client.close.assert_not_called()

    async def test_metadata_can_use_an_independently_configured_index(self) -> None:
        """Use the same provider class for document metadata and Markdown."""
        index = SearchIndex(name="metadata", fields=self.index.fields)
        client = MagicMock(spec=SearchClient)
        client.upload_documents = AsyncMock(side_effect=success)
        metadata_store = AzureAISearchStore(client, index)
        await metadata_store.store_metadata({"approved": False}, metadata_mapper=lambda metadata: {"key": "doc", "details": metadata})
        client.upload_documents.assert_awaited_once_with(documents=[{"key": "doc", "details": {"approved": False}}])
        self.client.upload_documents.assert_not_called()

    async def test_instances_may_share_the_same_index(self) -> None:
        """Do not impose a cross-role restriction on index names."""
        metadata_store = AzureAISearchStore(self.client, self.index)
        await metadata_store.store_metadata({}, metadata_mapper=lambda metadata: {"key": "metadata-1"})
        await self.store.store_markdown([self.chunk], chunk_mapper=lambda chunk: {"key": "chunk-1"})
        self.assertEqual(self.client.upload_documents.await_count, 2)

    async def test_batches_at_one_thousand_documents_and_keeps_order(self) -> None:
        """Write exact service batch boundaries using caller-supplied keys."""
        for size, expected_sizes in ((1000, [1000]), (1001, [1000, 1])):
            with self.subTest(size=size):
                self.client.upload_documents.reset_mock()
                positions = count()
                await self.store.store_markdown([self.chunk] * size, chunk_mapper=lambda chunk: {"key": str(next(positions))})
                batches = [invocation.kwargs["documents"] for invocation in self.client.upload_documents.await_args_list]
                self.assertEqual([len(batch) for batch in batches], expected_sizes)
                self.assertEqual([document["key"] for batch in batches for document in batch], [str(position) for position in range(size)])

    async def test_invalid_keys_are_rejected_before_any_uploads(self) -> None:
        """Reject missing, empty, non-string, and duplicate document keys."""
        documents: list[dict[str, object]] = [{}, {"key": ""}, {"key": None}, {"key": 1}]
        for document in documents:
            with self.subTest(document=document):
                with self.assertRaisesRegex(ValueError, "string key"):
                    await self.store.store_metadata({}, metadata_mapper=lambda metadata: document)
        with self.assertRaisesRegex(ValueError, "Duplicate"):
            await self.store.store_markdown([self.chunk] * 1001, chunk_mapper=lambda chunk: {"key": "duplicate"})
        self.client.upload_documents.assert_not_called()

    async def test_failed_indexing_results_raise_without_closing_caller_client(self) -> None:
        """Propagate per-document failures with status and service detail."""
        self.client.upload_documents.side_effect = None
        self.client.upload_documents.return_value = [IndexingResult.deserialize({"key": "failed", "status": False, "statusCode": 400, "errorMessage": "invalid vector"})]
        with self.assertRaisesRegex(RuntimeError, "failed.*400.*invalid vector"):
            await self.store.store_markdown([self.chunk], chunk_mapper=lambda chunk: {"key": "failed"})
        self.client.__aexit__.assert_not_called()
        self.client.close.assert_not_called()

    async def test_missing_duplicate_extra_and_unexpected_results_raise(self) -> None:
        """Require exactly one successful response for each uploaded key."""
        self.client.upload_documents.side_effect = None
        for keys in ([], ["one"], ["one", "one"], ["wrong", "other"], ["one", "two", "extra"]):
            with self.subTest(keys=keys):
                self.client.upload_documents.return_value = success([{"key": key} for key in keys])
                mapper = Mock(side_effect=[{"key": "one"}, {"key": "two"}])
                with self.assertRaisesRegex(RuntimeError, "do not match"):
                    await self.store.store_markdown([self.chunk, self.chunk], chunk_mapper=mapper)

    async def test_out_of_order_successes_are_accepted(self) -> None:
        """Correlate responses by keys rather than response positions."""
        self.client.upload_documents.side_effect = lambda documents: list(reversed(success(documents)))
        mapper = Mock(side_effect=[{"key": "one"}, {"key": "two"}])
        await self.store.store_markdown([self.chunk, self.chunk], chunk_mapper=mapper)
        self.client.upload_documents.assert_awaited_once()

    async def test_upload_errors_propagate_without_closing_caller_client(self) -> None:
        """Preserve original SDK errors and the caller's client lifetime."""
        error = HttpResponseError("upload failed")
        self.client.upload_documents.side_effect = error
        with self.assertRaises(HttpResponseError) as raised:
            await self.store.store_metadata({}, metadata_mapper=lambda metadata: {"key": "one"})
        self.assertIs(raised.exception, error)
        self.client.__aexit__.assert_not_called()
        self.client.close.assert_not_called()


class JsonResponse(AsyncHttpResponse):
    """Supply serialized indexing results to the real Azure SDK."""

    def __init__(self, request: HttpRequest, payload: object, *, status_code: int = 200) -> None:
        """Initialize a JSON response with a caller-selected HTTP status."""
        super().__init__(request, None)
        self.status_code = status_code
        self.headers = {"content-type": "application/json"}
        self.content_type = "application/json"
        self._body = json.dumps(payload).encode()

    def body(self) -> bytes:
        """Return the serialized response body."""
        return self._body

    async def load_body(self) -> None:
        """Retain the already buffered body."""


class RecordingTransport(AsyncHttpTransport):
    """Capture real SDK requests without contacting Azure."""

    def __init__(self) -> None:
        """Initialize captured document uploads."""
        self.uploads: list[dict[str, object]] = []
        self.status_code = 200
        self.closed = False

    async def open(self) -> None:
        """Open the in-memory transport without external resources."""

    async def close(self) -> None:
        """Close the in-memory transport without external resources."""
        self.closed = True

    async def __aenter__(self) -> "RecordingTransport":
        """Return this transport as an asynchronous context manager."""
        return self

    async def __aexit__(self, *args: object) -> None:
        """Close this transport on context exit."""
        await self.close()

    async def send(self, request: HttpRequest, **kwargs: object) -> AsyncHttpResponse:
        """Accept only document uploads and return matching indexing results."""
        if self.closed:
            raise AssertionError("the caller-owned transport was closed")
        if request.method != "POST" or "/docs/search.index" not in request.url:
            raise AssertionError(f"unexpected request: {request.method} {request.url}")
        if not isinstance(request.body, (str, bytes, bytearray)):
            raise AssertionError("expected a serialized JSON request")
        payload = json.loads(request.body)
        self.uploads.append(payload)
        if self.status_code != 200:
            return JsonResponse(request, {"error": {"code": "ServiceUnavailable", "message": "temporary failure"}}, status_code=self.status_code)
        return JsonResponse(request, {"value": [{"key": document["key"], "status": True, "statusCode": 201} for document in payload["value"]]})


class AzureAISearchSdkTests(unittest.IsolatedAsyncioTestCase):
    """Exercise document serialization through the actual Azure Search SDK."""

    async def test_real_sdk_serializes_chunks_vectors_and_metadata(self) -> None:
        """Write both independent roles without any index management requests."""
        transport = RecordingTransport()
        endpoint = "https://example.search.windows.net"
        credential = AzureKeyCredential("test-key")
        chunk_client = SearchClient(endpoint, "chunks", credential, transport=transport, retry_total=0)
        metadata_client = SearchClient(endpoint, "metadata", credential, transport=transport, retry_total=0)
        self.addAsyncCleanup(chunk_client.close)
        self.addAsyncCleanup(metadata_client.close)
        fields = [SimpleField(name="key", type="Edm.String", key=True)]
        markdown_store = AzureAISearchStore(chunk_client, SearchIndex(name="chunks", fields=fields))
        metadata_store = AzureAISearchStore(metadata_client, SearchIndex(name="metadata", fields=fields))

        await metadata_store.store_metadata({"approved": False}, metadata_mapper=lambda metadata: {"key": "doc", "details": metadata})
        await markdown_store.store_markdown([EmbeddedChunk("# Source", "Source", [1.0, 2.0])], chunk_mapper=lambda chunk: {"key": "chunk", "source": chunk.original_text, "input": chunk.embedding_text, "vector": chunk.embedding})

        self.assertFalse(transport.closed)
        self.assertEqual(transport.uploads, [{"value": [{"@search.action": "upload", "key": "doc", "details": {"approved": False}}]}, {"value": [{"@search.action": "upload", "key": "chunk", "source": "# Source", "input": "Source", "vector": [1.0, 2.0]}]}])

    async def test_given_configured_client_when_upload_fails_then_preserves_transport_retries_and_reuse(self) -> None:
        """Use the real SDK without bypassing client construction in the store."""
        transport = RecordingTransport()
        transport.status_code = 503
        client = SearchClient("https://example.search.windows.net", "metadata", AzureKeyCredential("test-key"), transport=transport, retry_total=0)
        self.addAsyncCleanup(client.close)
        store = AzureAISearchStore(client, SearchIndex(name="metadata", fields=[SimpleField(name="key", type="Edm.String", key=True)]))

        with self.assertRaises(HttpResponseError):
            await store.store_metadata({}, metadata_mapper=lambda metadata: {"key": "doc"})

        self.assertEqual(len(transport.uploads), 1)
        self.assertFalse(transport.closed)
        transport.status_code = 200

        await store.store_metadata({}, metadata_mapper=lambda metadata: {"key": "doc"})

        self.assertEqual(len(transport.uploads), 2)
        self.assertFalse(transport.closed)


if __name__ == "__main__":
    unittest.main()
