"""Tests for parameterized Azure SQL writes and native vector binding."""

import json
import unittest
from unittest.mock import AsyncMock, MagicMock, Mock

from azure.search.documents.aio import SearchClient
from azure.search.documents.indexes.models import SearchIndex, SimpleField
from azure.search.documents.models import IndexingResult
from sqlalchemy import JSON, Column, Integer, MetaData, String, Table, UnicodeText, select
from sqlalchemy.dialects import mssql
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncConnection
from sqlalchemy.schema import CreateTable
from sqlalchemy.sql.dml import Insert, Update
from sqlalchemy.sql.selectable import Select

from ingestra.chunker import BaseChunker, Chunk
from ingestra.converter import BaseConverter
from ingestra.embeddings import BaseEmbeddings
from ingestra.pipeline import EmbeddedChunk, Pipeline
from ingestra.store import AzureAISearchStore, AzureSQLStore, AzureSQLVector, BaseMarkdownStore, BaseMetadataStore


class AzureSQLVectorTests(unittest.TestCase):
    """Verify native vector SQL compilation and strict JSON transport."""

    def test_native_type_and_bound_cast(self) -> None:
        """Declare native vectors and never interpolate their values into SQL."""
        table = Table("chunks", MetaData(), Column("id", String(64), primary_key=True), Column("embedding", AzureSQLVector(2)))
        self.assertIn("embedding VECTOR(2)", str(CreateTable(table).compile(dialect=mssql.dialect())))
        statement = table.insert().values(id="one", embedding=[1.0, 2.0]).compile(dialect=mssql.dialect())
        self.assertIn("CAST(:embedding AS VECTOR(2))", str(statement))
        self.assertNotIn("[1.0, 2.0]", str(statement))
        self.assertEqual(statement.params["embedding"], [1.0, 2.0])
        self.assertIn("CAST(chunks.embedding AS NVARCHAR(max))", str(select(table.c.embedding).compile(dialect=mssql.dialect())))

    def test_vector_processors_round_trip_and_preserve_null(self) -> None:
        """Serialize finite numeric lists and decode vector JSON."""
        vector = AzureSQLVector(2)
        encode = vector.bind_processor(mssql.dialect())
        decode = vector.result_processor(mssql.dialect(), None)
        self.assertEqual(json.loads(encode([1, 2.5]) or ""), [1.0, 2.5])
        self.assertEqual(decode("[1.0, 2.5]"), [1.0, 2.5])
        self.assertIsNone(encode(None))
        self.assertIsNone(decode(None))
        self.assertEqual(AzureSQLVector(1).dimensions, 1)
        self.assertEqual(AzureSQLVector(1998).dimensions, 1998)

    def test_invalid_dimensions_are_rejected(self) -> None:
        """Reject invalid native float32 vector declarations."""
        for dimensions in (0, -1, 1999, True):
            with self.subTest(dimensions=dimensions):
                with self.assertRaisesRegex(ValueError, "between 1 and 1998"):
                    AzureSQLVector(dimensions)

    def test_invalid_embeddings_are_rejected(self) -> None:
        """Reject mismatched dimensions and non-finite values."""
        encode = AzureSQLVector(2).bind_processor(mssql.dialect())
        for vector in ([], [1.0], [1.0, float("nan")], [float("inf"), 2.0]):
            with self.subTest(vector=vector):
                with self.assertRaises(ValueError):
                    encode(vector)
        with self.assertRaises(TypeError):
            encode([True, 2.0])

    def test_invalid_vector_results_raise_explicitly(self) -> None:
        """Reject unsupported result encodings and malformed vector JSON."""
        decode = AzureSQLVector(2).result_processor(mssql.dialect(), None)
        with self.assertRaisesRegex(TypeError, "JSON strings"):
            decode(b"[1, 2]")
        for value in ("invalid-json", "[1]", "[1, NaN]"):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    decode(value)


class AzureSQLStoreTests(unittest.IsolatedAsyncioTestCase):
    """Verify caller-owned transactional SQL writes for both roles."""

    def setUp(self) -> None:
        """Prepare native vector and metadata tables with a mocked connection."""
        self.connection = Mock(spec=AsyncConnection)
        self.connection.dialect = mssql.dialect()
        self.connection.in_transaction.return_value = True
        self.lookup_result = Mock()
        self.lookup_result.first.return_value = None
        self.connection.execute = AsyncMock(return_value=self.lookup_result)
        metadata = MetaData()
        self.chunks = Table("chunks", metadata, Column("key", String(64), primary_key=True), Column("document_id", String(64)), Column("position", Integer), Column("markdown", UnicodeText), Column("embedding_text", UnicodeText), Column("embedding", AzureSQLVector(2)), schema="ingest")
        self.metadata = Table("metadata", metadata, Column("key", String(64), primary_key=True), Column("title", UnicodeText), Column("details", JSON), schema="ingest")
        self.chunk = EmbeddedChunk("# Source", "Source", [1.0, 2.0])
        self.store = AzureSQLStore(self.connection, self.chunks)

    def test_supports_both_contracts_without_queries(self) -> None:
        """Keep construction local and support either configured role."""
        self.assertIsInstance(self.store, BaseMarkdownStore)
        self.assertIsInstance(self.store, BaseMetadataStore)
        self.connection.execute.assert_not_called()

    async def test_inserts_chunk_text_and_native_embedding_with_bound_values(self) -> None:
        """Persist the complete mapped chunk without adding schema fields."""
        document: dict[str, object] = {"key": "one", "document_id": "doc", "position": 0, "markdown": self.chunk.original_text, "embedding_text": self.chunk.embedding_text, "embedding": self.chunk.embedding}
        await self.store.store_markdown([self.chunk], chunk_mapper=lambda chunk: document)
        lookup, insert = [invocation.args[0] for invocation in self.connection.execute.await_args_list]
        self.assertIsInstance(lookup, Select)
        self.assertIn("WITH (UPDLOCK, HOLDLOCK)", str(lookup.compile(dialect=mssql.dialect())))
        self.assertIsInstance(insert, Insert)
        compiled = insert.compile(dialect=mssql.dialect())
        self.assertEqual(compiled.params, document)
        self.assertIn("CAST(:embedding AS VECTOR(2))", str(compiled))
        self.connection.commit.assert_not_called()
        self.connection.rollback.assert_not_called()
        self.connection.close.assert_not_called()

    async def test_updates_existing_rows_without_inserting_again(self) -> None:
        """Make stable-key retries update existing records."""
        self.lookup_result.first.return_value = ("doc",)
        store = AzureSQLStore(self.connection, self.metadata)
        await store.store_metadata({"title": "new"}, metadata_mapper=lambda metadata: {"key": "doc", "title": metadata["title"]})
        lookup, update = [invocation.args[0] for invocation in self.connection.execute.await_args_list]
        self.assertIsInstance(lookup, Select)
        self.assertIsInstance(update, Update)
        self.assertIn("SET title=:title", str(update.compile(dialect=mssql.dialect())))
        self.assertNotIn("SET [key]", str(update.compile(dialect=mssql.dialect())))

    async def test_existing_key_only_metadata_needs_no_update(self) -> None:
        """Avoid invalid empty SET clauses for already existing key-only rows."""
        self.lookup_result.first.return_value = ("doc",)
        store = AzureSQLStore(self.connection, self.metadata)
        await store.store_metadata({}, metadata_mapper=lambda metadata: {"key": "doc"})
        self.assertEqual(self.connection.execute.await_count, 1)

    async def test_given_aliased_composite_key_when_upserting_then_uses_column_keys(self) -> None:
        """Use mapper keys consistently while rendering the database column names."""
        table = Table("aliased", MetaData(), Column("tenant_id", String(64), key="tenant", primary_key=True), Column("document_id", String(64), key="id", primary_key=True), Column("document_title", UnicodeText, key="title"))
        store = AzureSQLStore(self.connection, table)
        document: dict[str, object] = {"tenant": "tenant-1", "id": "doc-1", "title": "Report"}
        for existing in (None, ("tenant-1", "doc-1")):
            with self.subTest(existing=existing):
                self.connection.execute.reset_mock()
                self.lookup_result.first.return_value = existing

                await store.store_metadata({}, metadata_mapper=lambda metadata: document)

                lookup, write = [call.args[0] for call in self.connection.execute.await_args_list]
                lookup_sql = str(lookup.compile(dialect=mssql.dialect()))
                self.assertIn("aliased.tenant_id =", lookup_sql)
                self.assertIn("aliased.document_id =", lookup_sql)
                compiled = write.compile(dialect=mssql.dialect())
                if existing is None:
                    self.assertIsInstance(write, Insert)
                    self.assertEqual(compiled.params, document)
                else:
                    self.assertIsInstance(write, Update)
                    self.assertIn("SET document_title=:title", str(compiled))
                    self.assertNotIn("SET tenant_id", str(compiled))
                    self.assertNotIn("SET document_id", str(compiled))
        self.connection.commit.assert_not_called()

    async def test_metadata_supports_json_and_parameterized_untrusted_values(self) -> None:
        """Pass nested metadata and text values through SQLAlchemy bindings."""
        title = "x'; DROP TABLE ingest.chunks; --"
        store = AzureSQLStore(self.connection, self.metadata)
        await store.store_metadata({"approved": False}, metadata_mapper=lambda metadata: {"key": "doc", "title": title, "details": metadata})
        statement = self.connection.execute.await_args_list[-1].args[0].compile(dialect=mssql.dialect())
        self.assertNotIn(title, str(statement))
        self.assertEqual(statement.params, {"key": "doc", "title": title, "details": {"approved": False}})

    async def test_composite_primary_keys_are_used_in_locked_lookup(self) -> None:
        """Honor all key columns rather than assuming an identifier name."""
        table = Table("composite", MetaData(), Column("tenant", String(64), primary_key=True), Column("source", String(64), primary_key=True), Column("title", UnicodeText))
        store = AzureSQLStore(self.connection, table)
        await store.store_metadata({}, metadata_mapper=lambda metadata: {"tenant": "a", "source": "b", "title": "value"})
        lookup = self.connection.execute.await_args_list[0].args[0].compile(dialect=mssql.dialect())
        self.assertIn("WITH (UPDLOCK, HOLDLOCK)", str(lookup))
        self.assertEqual(set(lookup.params.values()), {"a", "b"})
        self.assertIn("composite.tenant =", str(lookup))
        self.assertIn("composite.source =", str(lookup))

    async def test_requires_active_caller_transaction(self) -> None:
        """Prevent successful-looking writes that the caller never commits."""
        self.connection.in_transaction.return_value = False
        with self.assertRaisesRegex(ValueError, "active transaction"):
            await self.store.store_markdown([self.chunk], chunk_mapper=lambda chunk: {"key": "one"})
        self.connection.execute.assert_not_called()

    async def test_validates_all_row_keys_and_column_names_before_writes(self) -> None:
        """Reject bad later rows before writing an earlier valid row."""
        for invalid in ({}, {"key": None}, {"key": "two", "unknown": 1}):
            with self.subTest(invalid=invalid):
                mapper = Mock(side_effect=[{"key": "one"}, invalid])
                with self.assertRaises(ValueError):
                    await self.store.store_markdown([self.chunk, self.chunk], chunk_mapper=mapper)
        self.connection.execute.assert_not_called()

    async def test_errors_propagate_without_owning_the_transaction(self) -> None:
        """Let the caller's context manager roll back failed SQL operations."""
        error = SQLAlchemyError("write failed")
        self.connection.execute.side_effect = error
        with self.assertRaises(SQLAlchemyError) as raised:
            await self.store.store_markdown([self.chunk], chunk_mapper=lambda chunk: {"key": "one"})
        self.assertIs(raised.exception, error)
        self.connection.commit.assert_not_called()
        self.connection.rollback.assert_not_called()
        self.connection.close.assert_not_called()

    async def test_insert_failures_propagate_after_the_locked_lookup(self) -> None:
        """Do not report success when the write fails after a successful lookup."""
        error = SQLAlchemyError("insert failed")
        self.connection.execute.side_effect = [self.lookup_result, error]
        with self.assertRaises(SQLAlchemyError) as raised:
            await self.store.store_markdown([self.chunk], chunk_mapper=lambda chunk: {"key": "one", "embedding": chunk.embedding})
        self.assertIs(raised.exception, error)
        self.assertEqual(self.connection.execute.await_count, 2)
        self.connection.commit.assert_not_called()
        self.connection.rollback.assert_not_called()
        self.connection.close.assert_not_called()

    def test_rejects_missing_primary_key_and_wrong_dialect(self) -> None:
        """Require an explicit SQL Server upsert identity."""
        with self.assertRaisesRegex(ValueError, "primary key"):
            AzureSQLStore(self.connection, Table("invalid", MetaData(), Column("value", UnicodeText)))
        self.connection.dialect = Mock(name="sqlite")
        with self.assertRaisesRegex(ValueError, "SQL Server"):
            AzureSQLStore(self.connection, self.chunks)

    async def test_all_four_backend_combinations(self) -> None:
        """Route a full pipeline ingestion independently to Search or SQL."""
        clients = {name: MagicMock(spec=SearchClient) for name in ("chunks", "metadata")}
        uploads = Mock()
        for name, client in clients.items():
            client.upload_documents = AsyncMock(side_effect=lambda documents: [IndexingResult.deserialize({"key": document["key"], "status": True, "statusCode": 201}) for document in documents])
            uploads.attach_mock(client.upload_documents, name)
        fields = [SimpleField(name="key", type="Edm.String", key=True)]
        converter = Mock(spec=BaseConverter)
        converter.convert = AsyncMock(return_value=("# Source", {"title": "document"}))
        chunker = Mock(spec=BaseChunker)
        chunker.chunk.return_value = [Chunk("# Source", "Source")]
        embeddings = Mock(spec=BaseEmbeddings)
        embeddings.generate = AsyncMock(return_value=[[1.0, 2.0]])
        for markdown_backend in ("search", "sql"):
            for metadata_backend in ("search", "sql"):
                with self.subTest(markdown=markdown_backend, metadata=metadata_backend):
                    uploads.reset_mock()
                    self.connection.execute.reset_mock()
                    markdown_store: BaseMarkdownStore = AzureAISearchStore(clients["chunks"], SearchIndex(name="chunks", fields=fields)) if markdown_backend == "search" else AzureSQLStore(self.connection, self.chunks)
                    metadata_store: BaseMetadataStore = AzureAISearchStore(clients["metadata"], SearchIndex(name="metadata", fields=fields)) if metadata_backend == "search" else AzureSQLStore(self.connection, self.metadata)
                    pipeline = Pipeline(converter, chunker, embeddings, markdown_store=markdown_store, metadata_store=metadata_store)
                    result = await pipeline.ingest(b"document", chunk_mapper=lambda chunk: {"key": "chunk", "markdown": chunk.original_text, "embedding_text": chunk.embedding_text, "embedding": chunk.embedding}, metadata_mapper=lambda metadata: {"key": "doc", "title": metadata["title"]})
                    self.assertEqual(result.chunks, [self.chunk])
                    self.assertEqual(result.metadata, {"title": "document"})
                    self.assertEqual(len(uploads.mock_calls), (markdown_backend == "search") + (metadata_backend == "search"))
                    self.assertEqual(self.connection.execute.await_count, 2 * ((markdown_backend == "sql") + (metadata_backend == "sql")))
                    expected_metadata: dict[str, object] = {"key": "doc", "title": "document"}
                    expected_chunk: dict[str, object] = {"key": "chunk", "markdown": "# Source", "embedding_text": "Source", "embedding": [1.0, 2.0]}
                    search_targets: list[str] = []
                    search_payloads: list[list[dict[str, object]]] = []
                    sql_rows: dict[str, dict[str, object]] = {}
                    if metadata_backend == "search":
                        search_targets.append("metadata")
                        search_payloads.append([expected_metadata])
                    else:
                        sql_rows["metadata"] = expected_metadata
                    if markdown_backend == "search":
                        search_targets.append("chunks")
                        search_payloads.append([expected_chunk])
                    else:
                        sql_rows["chunks"] = expected_chunk
                    self.assertEqual([invocation[0] for invocation in uploads.mock_calls], search_targets)
                    self.assertEqual([invocation.kwargs["documents"] for invocation in uploads.mock_calls], search_payloads)
                    inserts = [invocation.args[0] for invocation in self.connection.execute.await_args_list if isinstance(invocation.args[0], Insert)]
                    self.assertEqual({statement.table.name: statement.compile(dialect=mssql.dialect()).params for statement in inserts}, sql_rows)


if __name__ == "__main__":
    unittest.main()
