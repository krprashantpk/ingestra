"""Verify pipeline ingestion, SQL mapping, and transaction ownership."""

import struct
import unittest
from hashlib import sha256
from unittest.mock import AsyncMock, Mock, patch

from azure.ai.contentunderstanding.models import AnalysisResult
from azure.core.credentials import AccessToken
from sqlalchemy.dialects import mssql
from sqlalchemy.exc import SQLAlchemyError

from ingestra.chunker import Chunk, MarkdownTokenChunker
from ingestra.converter import AzureContentUnderstandingConverter
from ingestra.pipeline import Pipeline
from services import ingestion
from utilities.database import EMBEDDING_DIMENSIONS, chunks, create_sql_engine, documents


class IngestionTests(unittest.IsolatedAsyncioTestCase):
    """Run the real pipeline and SQL stores with mocked external clients."""

    def setUp(self) -> None:
        """Configure processing results, an active SQL transaction, and clients."""
        environment = patch.dict("os.environ", {
            "AZURE_CONTENT_UNDERSTANDING_ENDPOINT": "https://test.services.ai.azure.com",
            "AZURE_OPENAI_ENDPOINT": "https://test.openai.azure.com",
            "AZURE_SQL_SERVER": "test.database.windows.net",
            "AZURE_SQL_DATABASE": "ingestra",
        }, clear=True)
        environment.start()
        self.addCleanup(environment.stop)
        names = ("DefaultAzureCredential", "ContentUnderstandingClient", "AsyncAzureOpenAI", "create_sql_engine", "AzureContentUnderstandingConverter", "MarkdownTokenChunker", "AzureOpenAIEmbeddings")
        factories = []
        for name in names:
            replacement = patch(f"services.ingestion.{name}")
            factories.append(replacement.start())
            self.addCleanup(replacement.stop)
        credential_factory, self.content_client_factory, _, self.engine_factory, converter_factory, self.chunker_factory, embeddings_factory = factories
        credential_factory.return_value.__aenter__.return_value.get_token = AsyncMock(return_value=AccessToken("token", 9999999999))
        self.metadata = {"title": "Report", "nested": {"approved": True}}
        self.converter = converter_factory.return_value
        self.converter.convert = AsyncMock(return_value=("body", self.metadata))
        self.chunker = self.chunker_factory.return_value
        self.chunker.chunk.return_value = [Chunk("body", "context body", page_numbers=(2, 3))]
        self.embeddings = embeddings_factory.return_value
        self.embeddings.generate = AsyncMock(return_value=[[0.0] * EMBEDDING_DIMENSIONS])
        self.connection = Mock()
        self.connection.dialect = mssql.dialect()
        self.connection.in_transaction.return_value = True
        missing = Mock()
        missing.first.return_value = None
        self.connection.execute = AsyncMock(return_value=missing)
        self.engine = self.engine_factory.return_value
        self.engine.dispose = AsyncMock()
        self.transaction = self.engine.begin.return_value
        self.transaction.__aenter__ = AsyncMock(return_value=self.connection)
        self.transaction.__aexit__ = AsyncMock(return_value=False)

    async def test_given_no_api_version_when_ingested_then_uses_stable_content_understanding_api(self) -> None:
        """Keep custom analyzer lookup independent of the SDK preview default."""
        await ingestion.ingest_file(b"file", "report.pdf", "http:report.pdf")

        self.assertEqual(self.content_client_factory.call_args.kwargs["api_version"], "2025-11-01")

    async def test_given_api_version_override_when_ingested_then_uses_configured_content_understanding_api(self) -> None:
        """Honor an explicitly chosen API version without changing the analyzer."""
        with patch.dict("os.environ", {"AZURE_CONTENT_UNDERSTANDING_API_VERSION": "2026-06-01-preview"}):
            await ingestion.ingest_file(b"file", "report.pdf", "http:report.pdf")

        self.assertEqual(self.content_client_factory.call_args.kwargs["api_version"], "2026-06-01-preview")

    async def test_given_document_when_ingested_then_uses_separate_pipeline_stages(self) -> None:
        """Exercise conversion, Markdown chunking, and both public storage APIs."""
        with (
            patch.object(Pipeline, "convert", autospec=True, side_effect=Pipeline.convert) as convert,
            patch.object(Pipeline, "chunk", autospec=True, side_effect=Pipeline.chunk) as chunk,
            patch.object(Pipeline, "ingest_metadata", autospec=True, side_effect=Pipeline.ingest_metadata) as ingest_metadata,
            patch.object(Pipeline, "ingest_chunks", autospec=True, side_effect=Pipeline.ingest_chunks) as ingest_chunks,
        ):
            result = await ingestion.ingest_file(b"file", "report.pdf", "http:report.pdf")

        convert.assert_awaited_once()
        chunk.assert_awaited_once()
        ingest_metadata.assert_awaited_once()
        ingest_chunks.assert_awaited_once()
        self.assertEqual(convert.await_args.args[1], b"file")
        self.assertEqual(chunk.await_args.args[1], "body")
        self.assertIs(ingest_metadata.await_args.args[1], self.metadata)
        self.assertEqual(ingest_chunks.await_args.args[1][0].embedding_text, "context body")
        self.assertTrue(callable(ingest_chunks.await_args.kwargs["chunk_mapper"]))
        self.assertTrue(callable(ingest_metadata.await_args.kwargs["metadata_mapper"]))
        self.assertEqual(result, {"document_id": sha256(b"http:report.pdf").hexdigest(), "filename": "report.pdf", "chunks": 1})
        self.assertEqual(self.connection.execute.await_count, 5)
        self.transaction.__aexit__.assert_awaited_once_with(None, None, None)
        self.engine.dispose.assert_awaited_once()

    async def test_given_result_when_ingested_then_preserves_sql_roles_and_provenance(self) -> None:
        """Persist metadata and vectors through the pipeline's real SQL stores."""
        result = await ingestion.ingest_file(b"bytes", "report.pdf", "blob:documents/report.pdf")
        statements = [call.args[0] for call in self.connection.execute.await_args_list]
        metadata_row = statements[1].compile().params
        chunk_row = statements[3].compile().params

        self.assertEqual(result["document_id"], sha256(b"blob:documents/report.pdf").hexdigest())
        self.assertEqual(metadata_row["extracted_metadata"], self.metadata)
        self.assertEqual(metadata_row["content_sha256"], sha256(b"bytes").hexdigest())
        self.assertEqual(metadata_row["content_bytes"], 5)
        self.assertIsNotNone(metadata_row["ingested_at"].tzinfo)
        self.assertEqual(chunk_row["embedding"], [0.0] * EMBEDDING_DIMENSIONS)
        self.assertEqual(chunk_row["page_numbers"], [2, 3])
        self.assertEqual(chunk_row["embedding_text"], "context body")

    async def test_given_shorter_reupload_when_ingested_then_deletes_only_obsolete_document_chunks(self) -> None:
        """Retain current chunks and scope cleanup to this document's old tail."""
        result = await ingestion.ingest_file(b"file", "report.pdf", "http:report.pdf")
        cleanup = self.connection.execute.await_args.args[0]
        compiled = cleanup.compile(dialect=mssql.dialect())

        self.assertTrue(cleanup.is_delete)
        self.assertIn("document_id = :document_id_1", str(compiled))
        self.assertIn("chunk_index >= :chunk_index_1", str(compiled))
        self.assertEqual(compiled.params, {"document_id_1": result["document_id"], "chunk_index_1": 1})

    async def test_given_same_source_when_reingested_then_ids_are_stable(self) -> None:
        """Keep document and chunk identities stable across changed content."""
        first = await ingestion.ingest_file(b"old", "report.pdf", "http:report.pdf")
        second = await ingestion.ingest_file(b"new", "report.pdf", "http:report.pdf")
        inserted = [call.args[0].compile().params for call in self.connection.execute.await_args_list if call.args[0].is_insert and call.args[0].table.name == "document_chunks"]

        self.assertEqual(first["document_id"], second["document_id"])
        self.assertEqual([row["id"] for row in inserted], [f"{first['document_id']}:0"] * 2)

    async def test_given_multiple_chunks_when_ingested_then_indices_are_ordered(self) -> None:
        """Assign distinct stable IDs even when chunk text repeats."""
        self.chunker.chunk.return_value *= 2
        self.embeddings.generate.return_value *= 2

        result = await ingestion.ingest_file(b"file", "report.pdf", "http:report.pdf")
        inserted = [call.args[0].compile().params for call in self.connection.execute.await_args_list if call.args[0].is_insert and call.args[0].table.name == "document_chunks"]

        self.assertEqual([row["id"] for row in inserted], [f"{result['document_id']}:0", f"{result['document_id']}:1"])
        self.assertEqual([row["chunk_index"] for row in inserted], [0, 1])
        self.assertEqual(self.connection.execute.await_args.args[0].compile().params["chunk_index_1"], 2)

    async def test_given_processing_when_ingested_then_no_sql_writes_occur_during_analysis(self) -> None:
        """Acquire document locks only after remote processing completes."""
        async def convert(data: bytes) -> tuple[str, dict[str, object]]:
            """Confirm the pipeline has not executed SQL during conversion."""
            self.assertEqual(data, b"file")
            self.connection.execute.assert_not_called()
            return "body", self.metadata

        self.converter.convert.side_effect = convert

        await ingestion.ingest_file(b"file", "report.pdf", "http:report.pdf")

        self.connection.execute.assert_awaited()

    async def test_given_document_when_ingested_then_preserves_configured_chunk_budget(self) -> None:
        """Keep the 2048-token size goal with pipeline-managed storage."""
        await ingestion.ingest_file(b"file", "report.pdf", "http:report.pdf")

        self.chunker_factory.assert_called_once_with(chunk_size=2048)

    async def test_given_sql_failure_when_ingested_then_rolls_back_and_disposes(self) -> None:
        """Roll back failed chunk writes and obsolete-chunk cleanup alike."""
        missing = self.connection.execute.return_value
        for failure_at in (3, 4):
            with self.subTest(failure_at=failure_at):
                self.connection.execute.reset_mock()
                self.transaction.__aexit__.reset_mock()
                self.engine.dispose.reset_mock()
                error = SQLAlchemyError("write or cleanup failed")
                self.connection.execute.side_effect = [missing] * failure_at + [error]

                with self.assertRaises(SQLAlchemyError):
                    await ingestion.ingest_file(b"file", "report.pdf", "http:report.pdf")

                self.assertIs(self.transaction.__aexit__.await_args.args[1], error)
                self.engine.dispose.assert_awaited_once()

    async def test_given_processing_failure_when_ingested_then_rolls_back_without_sql_writes(self) -> None:
        """Let pipeline failures propagate without persisting either role."""
        error = RuntimeError("analysis failed")
        self.converter.convert.side_effect = error

        with self.assertRaises(RuntimeError):
            await ingestion.ingest_file(b"file", "report.pdf", "http:report.pdf")

        self.connection.execute.assert_not_called()
        self.assertIs(self.transaction.__aexit__.await_args.args[1], error)
        self.engine.dispose.assert_awaited_once()

    async def test_given_empty_conversion_when_ingested_then_rolls_back_metadata_without_deleting_chunks(self) -> None:
        """Do not commit metadata or remove existing data after empty extraction."""
        self.chunker.chunk.return_value = []

        with self.assertRaises(ingestion.EmptyExtractionError):
            await ingestion.ingest_file(b"file", "report.pdf", "http:report.pdf")

        statements = [call.args[0] for call in self.connection.execute.await_args_list]
        self.assertEqual(len(statements), 2)
        self.assertTrue(statements[1].is_insert)
        self.assertEqual(statements[1].table.name, "document_metadata")
        self.assertIs(self.transaction.__aexit__.await_args.args[0], ingestion.EmptyExtractionError)
        self.embeddings.generate.assert_not_called()
        self.engine.dispose.assert_awaited_once()

    async def test_given_whitespace_extraction_when_reingested_then_rolls_back_without_replacing_chunks(self) -> None:
        """Exercise real conversion and chunking before the existing-data safeguard."""
        poller = Mock()
        poller.result = AsyncMock(return_value=AnalysisResult({"contents": [{"kind": "document", "markdown": " \n\t\n"}]}))
        client = Mock()
        client.begin_analyze_binary = AsyncMock(return_value=poller)
        converter = AzureContentUnderstandingConverter(client, "test-analyzer")
        self.chunker_factory.return_value = MarkdownTokenChunker(tokenizer=len)

        with patch("services.ingestion.AzureContentUnderstandingConverter", return_value=converter):
            with self.assertRaises(ingestion.EmptyExtractionError):
                await ingestion.ingest_file(b"file", "existing.pdf", "http:existing.pdf")

        statements = [call.args[0] for call in self.connection.execute.await_args_list]
        self.assertEqual(len(statements), 2)
        self.assertTrue(statements[0].is_select)
        self.assertTrue(statements[1].is_insert)
        self.assertEqual(statements[1].table.name, "document_metadata")
        self.assertIs(self.transaction.__aexit__.await_args.args[0], ingestion.EmptyExtractionError)
        self.embeddings.generate.assert_not_called()
        self.engine.dispose.assert_awaited_once()

    def test_given_exact_limit_when_validated_then_accepts_input(self) -> None:
        """Allow exactly 20 MiB rather than imposing an off-by-one limit."""
        ingestion.validate_file(b"x" * ingestion.MAX_FILE_BYTES, "report.pdf")


class DatabaseTests(unittest.TestCase):
    """Verify the shared SQL schema and connection configuration."""

    def test_given_tables_when_defined_then_vectors_and_foreign_keys_match(self) -> None:
        """Declare native vectors rather than a JSON embedding fallback."""
        self.assertEqual(chunks.c.embedding.type.get_col_spec(), "VECTOR(1536)")
        self.assertEqual(next(iter(chunks.c.document_id.foreign_keys)).column, documents.c.document_id)

    def test_given_access_token_when_engine_created_then_uses_encrypted_odbc_and_binary_token(self) -> None:
        """Keep SQL password and connection-string token authentication disabled."""
        with patch("utilities.database.create_async_engine") as factory:
            create_sql_engine("test.database.windows.net", "ingestra", "access-token")

        args, kwargs = factory.call_args
        odbc = args[0].query["odbc_connect"]
        token = kwargs["connect_args"]["attrs_before"][1256]
        length = struct.unpack("<I", token[:4])[0]
        self.assertEqual(token[4:].decode("utf-16-le"), "access-token")
        self.assertEqual(length, len(token) - 4)
        self.assertIn("Encrypt=yes;TrustServerCertificate=no", odbc)
        self.assertIn("LongAsMax=Yes;", odbc)
        self.assertNotIn("Trusted_Connection", odbc)
        self.assertNotIn("access-token", str(args[0]))
