"""Exercise HTTP validation, Blob delivery, and provider failure responses."""

import json
import unittest
from unittest.mock import AsyncMock, Mock, patch

import azure.functions as func
from azure.core.exceptions import AzureError

import function_app
from services.ingestion import MAX_FILE_BYTES, EmptyExtractionError


class TriggerTests(unittest.IsolatedAsyncioTestCase):
    """Verify the trigger contracts without calling any Azure service."""

    def setUp(self) -> None:
        """Replace the shared ingestion boundary for each trigger test."""
        self.ingest_patch = patch("function_app.ingest_file", new_callable=AsyncMock)
        self.ingest = self.ingest_patch.start()
        self.addCleanup(self.ingest_patch.stop)

    def request(self, body: bytes = b"document", filename: str = "report.pdf") -> func.HttpRequest:
        """Construct a raw upload request."""
        return func.HttpRequest("POST", "https://localhost/api/ingest", body=body, params={"filename": filename})

    async def test_given_raw_upload_when_http_then_returns_document_and_chunk_count(self) -> None:
        """Return only the confirmed ingestion result."""
        self.ingest.return_value = {"document_id": "abc", "chunks": 2}

        response = await function_app.ingest_http(self.request())

        self.assertEqual(response.status_code, 200)
        self.assertEqual(json.loads(response.get_body()), {"document_id": "abc", "chunks": 2})
        self.ingest.assert_awaited_once_with(b"document", "report.pdf", "http:report.pdf")

    async def test_given_invalid_upload_when_http_then_rejects_before_ingestion(self) -> None:
        """Reject missing filenames and empty bodies."""
        for body, filename in ((b"", "report.pdf"), (b"x", ""), (b"x", "  "), (b"x", "x" * 1025)):
            with self.subTest(filename=filename):
                response = await function_app.ingest_http(self.request(body, filename))

                self.assertEqual(response.status_code, 400)
                self.assertIn("error", json.loads(response.get_body()))
        self.ingest.assert_not_called()

    async def test_given_oversized_upload_when_http_then_returns_413(self) -> None:
        """Apply the exact byte limit, not an estimated content length."""
        response = await function_app.ingest_http(self.request(b"x" * (MAX_FILE_BYTES + 1)))

        self.assertEqual(response.status_code, 413)
        self.ingest.assert_not_called()

    async def test_given_empty_extraction_when_http_then_returns_422(self) -> None:
        """Do not report a successful ingestion when conversion yielded no chunks."""
        self.ingest.side_effect = EmptyExtractionError("No usable chunks")

        response = await function_app.ingest_http(self.request())

        self.assertEqual(response.status_code, 422)

    async def test_given_provider_failure_when_http_then_returns_502_without_secrets(self) -> None:
        """Keep internal provider details out of the response."""
        self.ingest.side_effect = AzureError("sensitive provider details")

        with self.assertLogs("function_app", level="ERROR"):
            response = await function_app.ingest_http(self.request())

        self.assertEqual(response.status_code, 502)
        self.assertNotIn("sensitive", response.get_body().decode())

    async def test_given_blob_when_triggered_then_uses_blob_source_and_bounded_read(self) -> None:
        """Keep the complete blob path as its stable source identity."""
        blob = Mock(spec=func.InputStream, name="blob")
        blob.name = "documents/folder/report.pdf"
        blob.length = 8
        blob.read.return_value = b"document"

        await function_app.ingest_blob(blob)

        blob.read.assert_called_once_with(size=MAX_FILE_BYTES + 1)
        self.ingest.assert_awaited_once_with(b"document", "report.pdf", "blob:documents/folder/report.pdf")

    async def test_given_oversized_blob_when_triggered_then_raises_for_retry(self) -> None:
        """Reject an oversized blob before allocating its content."""
        blob = Mock(spec=func.InputStream)
        blob.name = "documents/large.pdf"
        blob.length = MAX_FILE_BYTES + 1

        with self.assertRaises(ValueError), self.assertLogs("function_app", level="ERROR"):
            await function_app.ingest_blob(blob)

        blob.read.assert_not_called()

    async def test_given_provider_failure_when_blob_triggered_then_propagates_for_retry(self) -> None:
        """Preserve the original failure so the runtime cannot acknowledge success."""
        blob = Mock(spec=func.InputStream)
        blob.name = "documents/report.pdf"
        blob.length = 8
        blob.read.return_value = b"document"
        self.ingest.side_effect = AzureError("provider unavailable")

        with self.assertRaises(AzureError), self.assertLogs("function_app", level="ERROR"):
            await function_app.ingest_blob(blob)

    def test_given_decorators_when_indexed_then_auth_and_event_source_are_configured(self) -> None:
        """Verify the actual Azure Functions binding output."""
        functions = {function.get_function_name(): json.loads(function.get_function_json()) for function in function_app.app.get_functions()}
        http = next(binding for binding in functions["IngestHttp"]["bindings"] if binding["type"] == "httpTrigger")
        blob = functions["IngestBlob"]["bindings"][0]

        self.assertEqual(http["authLevel"], func.AuthLevel.FUNCTION.name)
        self.assertEqual(http["methods"], ["POST"])
        self.assertEqual(blob["source"], "EventGrid")
        self.assertEqual(blob["path"], "%INGEST_CONTAINER%/{name}")
