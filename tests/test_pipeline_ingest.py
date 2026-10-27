"""Tests for optional pipeline persistence and independent storage roles."""

import subprocess
import sys
import unittest
from typing import get_type_hints
from unittest.mock import AsyncMock, Mock, call

from ingestra.chunker import BaseChunker, Chunk
from ingestra.converter import BaseConverter
from ingestra.embeddings import BaseEmbeddings
from ingestra.pipeline import ChunkResult, EmbeddedChunk, Pipeline
from ingestra.store import BaseMarkdownStore, BaseMetadataStore
from ingestra.types import ChunkResult as SharedResult
from ingestra.types import EmbeddedChunk as SharedChunk


class RecordingStore(BaseMarkdownStore, BaseMetadataStore):
    """Capture real mapper execution without a service dependency."""

    def __init__(self) -> None:
        """Initialize captured storage documents."""
        self.documents: list[dict[str, object]] = []

    async def _store_documents(self, documents: list[dict[str, object]]) -> None:
        """Capture complete documents produced by the shared mapping contracts."""
        self.documents.extend(documents)


class PipelineIngestTests(unittest.IsolatedAsyncioTestCase):
    """Verify processing, validation, write ordering, and partial failures."""

    def setUp(self) -> None:
        """Configure processing components and independently mocked stores."""
        self.metadata: dict[str, object] = {"title": "Example", "approved": False}
        self.converter = Mock(spec=BaseConverter)
        self.converter.convert = AsyncMock(return_value=("# Source", self.metadata))
        self.chunker = Mock(spec=BaseChunker)
        self.chunker.chunk.return_value = [Chunk("# Source", "Source")]
        self.embeddings = Mock(spec=BaseEmbeddings)
        self.embeddings.generate = AsyncMock(return_value=[[1.0, 2.0]])
        self.markdown_store = Mock(spec=BaseMarkdownStore)
        self.markdown_store.store_markdown = AsyncMock()
        self.metadata_store = Mock(spec=BaseMetadataStore)
        self.metadata_store.store_metadata = AsyncMock()
        self.chunk_mapper = Mock(return_value={"id": "chunk"})
        self.metadata_mapper = Mock(return_value={"id": "document"})
        self.pipeline = Pipeline(self.converter, self.chunker, self.embeddings, markdown_store=self.markdown_store, metadata_store=self.metadata_store)

    async def _ingest(self) -> ChunkResult:
        """Ingest a document using both configured stores and per-call mappers."""
        return await self.pipeline.ingest(b"document", chunk_mapper=self.chunk_mapper, metadata_mapper=self.metadata_mapper)

    async def test_given_embedded_chunks_when_ingest_chunks_then_only_stores_chunks(self) -> None:
        """Forward embedded chunks without processing or metadata persistence."""
        chunks = [EmbeddedChunk("# Source", "Source", [1.0, 2.0])]

        result = await self.pipeline.ingest_chunks(chunks, chunk_mapper=self.chunk_mapper)

        self.assertIsNone(result)
        self.markdown_store.store_markdown.assert_awaited_once_with(chunks, chunk_mapper=self.chunk_mapper)
        self.metadata_store.store_metadata.assert_not_called()
        self.converter.convert.assert_not_called()
        self.chunker.chunk.assert_not_called()
        self.embeddings.generate.assert_not_called()

    async def test_given_metadata_when_ingest_metadata_then_only_stores_metadata(self) -> None:
        """Forward document metadata without processing or chunk persistence."""
        result = await self.pipeline.ingest_metadata(self.metadata, metadata_mapper=self.metadata_mapper)

        self.assertIsNone(result)
        self.metadata_store.store_metadata.assert_awaited_once_with(self.metadata, metadata_mapper=self.metadata_mapper)
        self.markdown_store.store_markdown.assert_not_called()
        self.converter.convert.assert_not_called()
        self.chunker.chunk.assert_not_called()
        self.embeddings.generate.assert_not_called()

    async def test_given_no_markdown_store_when_ingest_chunks_then_rejects(self) -> None:
        """Require the matching store even when metadata storage is configured."""
        pipeline = Pipeline(self.converter, self.chunker, self.embeddings, metadata_store=self.metadata_store)

        with self.assertRaisesRegex(ValueError, "configured markdown_store"):
            await pipeline.ingest_chunks([], chunk_mapper=self.chunk_mapper)

        self.metadata_store.store_metadata.assert_not_called()
        self.converter.convert.assert_not_called()

    async def test_given_no_metadata_store_when_ingest_metadata_then_rejects(self) -> None:
        """Require the matching store even when chunk storage is configured."""
        pipeline = Pipeline(self.converter, self.chunker, self.embeddings, markdown_store=self.markdown_store)

        with self.assertRaisesRegex(ValueError, "configured metadata_store"):
            await pipeline.ingest_metadata(self.metadata, metadata_mapper=self.metadata_mapper)

        self.markdown_store.store_markdown.assert_not_called()
        self.converter.convert.assert_not_called()

    async def test_given_non_callable_mappers_when_ingesting_separately_then_rejects_before_storage(self) -> None:
        """Validate each role's mapper before forwarding to its store."""
        for mapper in (None, 42):
            with self.subTest(mapper=mapper):
                with self.assertRaisesRegex(TypeError, "chunk_mapper must be callable"):
                    await self.pipeline.ingest_chunks([], chunk_mapper=mapper)
                with self.assertRaisesRegex(TypeError, "metadata_mapper must be callable"):
                    await self.pipeline.ingest_metadata(self.metadata, metadata_mapper=mapper)

        self.markdown_store.store_markdown.assert_not_called()
        self.metadata_store.store_metadata.assert_not_called()

    async def test_given_only_markdown_store_when_ingest_chunks_then_maps_source_pages(self) -> None:
        """Persist prepared chunks without requiring a metadata store."""
        store = RecordingStore()
        pipeline = Pipeline(self.converter, self.chunker, self.embeddings, markdown_store=store)
        chunks = (EmbeddedChunk("Source", "Source", [1.0], page_numbers=(2, 3)),)

        await pipeline.ingest_chunks(chunks, chunk_mapper=lambda chunk: {"pages": list(chunk.page_numbers)})

        self.assertEqual(store.documents, [{"pages": [2, 3]}])

    async def test_given_empty_chunks_when_ingest_chunks_then_skips_mapping_and_writes(self) -> None:
        """Preserve the store's empty-chunk no-op guarantee."""
        store = RecordingStore()
        pipeline = Pipeline(self.converter, self.chunker, self.embeddings, markdown_store=store)

        await pipeline.ingest_chunks([], chunk_mapper=self.chunk_mapper)

        self.assertEqual(store.documents, [])
        self.chunk_mapper.assert_not_called()

    async def test_given_empty_metadata_and_only_metadata_store_when_ingest_metadata_then_writes(self) -> None:
        """Persist a mapped document even when extracted metadata is empty."""
        store = RecordingStore()
        pipeline = Pipeline(self.converter, self.chunker, self.embeddings, metadata_store=store)

        await pipeline.ingest_metadata({}, metadata_mapper=lambda metadata: {"id": "document", "metadata": metadata})

        self.assertEqual(store.documents, [{"id": "document", "metadata": {}}])

    async def test_given_chunk_store_error_when_ingest_chunks_then_propagates_unchanged(self) -> None:
        """Expose chunk persistence failures without touching metadata."""
        error = RuntimeError("chunks unavailable")
        self.markdown_store.store_markdown.side_effect = error

        with self.assertRaises(RuntimeError) as raised:
            await self.pipeline.ingest_chunks([EmbeddedChunk("Source", "Source", [1.0])], chunk_mapper=self.chunk_mapper)

        self.assertIs(raised.exception, error)
        self.metadata_store.store_metadata.assert_not_called()

    async def test_given_metadata_store_error_when_ingest_metadata_then_propagates_unchanged(self) -> None:
        """Expose metadata persistence failures without touching chunks."""
        error = RuntimeError("metadata unavailable")
        self.metadata_store.store_metadata.side_effect = error

        with self.assertRaises(RuntimeError) as raised:
            await self.pipeline.ingest_metadata(self.metadata, metadata_mapper=self.metadata_mapper)

        self.assertIs(raised.exception, error)
        self.markdown_store.store_markdown.assert_not_called()

    def test_shared_models_preserve_existing_imports_and_public_annotations(self) -> None:
        """Keep model identity and runtime-resolvable storage annotations."""
        self.assertIs(EmbeddedChunk, SharedChunk)
        self.assertIs(ChunkResult, SharedResult)
        hints = get_type_hints(Pipeline.__init__)
        self.assertEqual(hints["markdown_store"], BaseMarkdownStore | None)
        self.assertEqual(hints["metadata_store"], BaseMetadataStore | None)
        self.assertIs(get_type_hints(Pipeline.ingest)["return"], ChunkResult)

    def test_fresh_import_orders_do_not_form_cycles(self) -> None:
        """Keep processing, providers, and models importable in any initial order."""
        for module in ("ingestra.pipeline", "ingestra.store", "ingestra.types"):
            with self.subTest(first_import=module):
                code = (
                    f"import {module}; "
                    "from ingestra.pipeline import ChunkResult, EmbeddedChunk; "
                    "from ingestra.types import ChunkResult as Result, EmbeddedChunk as Chunk; "
                    "from ingestra.store import AzureAISearchStore, AzureSQLStore; "
                    "assert ChunkResult is Result; assert EmbeddedChunk is Chunk"
                )
                result = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, check=False)
                self.assertEqual(result.returncode, 0, result.stderr)

    async def test_runs_processing_then_metadata_then_markdown_and_returns_result(self) -> None:
        """Pass exact result values and callback identities to each store."""
        stages = Mock()
        stages.attach_mock(self.converter.convert, "convert")
        stages.attach_mock(self.chunker.chunk, "chunk")
        stages.attach_mock(self.embeddings.generate, "embed")
        stages.attach_mock(self.metadata_store.store_metadata, "metadata")
        stages.attach_mock(self.markdown_store.store_markdown, "markdown")
        result = await self._ingest()
        self.assertEqual(result, ChunkResult([EmbeddedChunk("# Source", "Source", [1.0, 2.0])], self.metadata))
        self.assertIs(result.metadata, self.metadata)
        self.assertEqual(stages.mock_calls, [call.convert(b"document"), call.chunk("# Source"), call.embed(["Source"]), call.metadata(result.metadata, metadata_mapper=self.metadata_mapper), call.markdown(result.chunks, chunk_mapper=self.chunk_mapper)])
        self.chunk_mapper.assert_not_called()
        self.metadata_mapper.assert_not_called()

    async def test_chunk_remains_side_effect_free_with_stores_configured(self) -> None:
        """Keep the existing chunk operation usable without storage callbacks."""
        result = await self.pipeline.chunk("# Source")
        self.assertEqual(result, [EmbeddedChunk("# Source", "Source", [1.0, 2.0])])
        self.converter.convert.assert_not_called()
        self.metadata_store.store_metadata.assert_not_called()
        self.markdown_store.store_markdown.assert_not_called()

    async def test_given_configured_stores_when_convert_then_does_not_write(self) -> None:
        """Keep conversion usable without storage callbacks or other stages."""
        result = await self.pipeline.convert(b"document")

        self.assertEqual(result, ("# Source", self.metadata))
        self.chunker.chunk.assert_not_called()
        self.embeddings.generate.assert_not_called()
        self.metadata_store.store_metadata.assert_not_called()
        self.markdown_store.store_markdown.assert_not_called()

    async def test_metadata_store_can_be_configured_alone(self) -> None:
        """Allow metadata persistence without configuring a Markdown store."""
        pipeline = Pipeline(self.converter, self.chunker, self.embeddings, metadata_store=self.metadata_store)
        result = await pipeline.ingest(b"document", metadata_mapper=self.metadata_mapper)
        self.metadata_store.store_metadata.assert_awaited_once_with(result.metadata, metadata_mapper=self.metadata_mapper)
        self.markdown_store.store_markdown.assert_not_called()
        self.assertEqual(len(result.chunks), 1)

    async def test_markdown_store_can_be_configured_alone(self) -> None:
        """Allow embedded-chunk persistence without configuring a metadata store."""
        pipeline = Pipeline(self.converter, self.chunker, self.embeddings, markdown_store=self.markdown_store)
        result = await pipeline.ingest(b"document", chunk_mapper=self.chunk_mapper)
        self.markdown_store.store_markdown.assert_awaited_once_with(result.chunks, chunk_mapper=self.chunk_mapper)
        self.metadata_store.store_metadata.assert_not_called()
        self.assertIs(result.metadata, self.metadata)

    async def test_source_page_numbers_are_available_to_storage_mappers(self) -> None:
        """Expose source pages to real storage callbacks after embedding."""
        self.chunker.chunk.return_value = [Chunk("# Source", "Source", page_numbers=(2, 3))]
        store = RecordingStore()
        pipeline = Pipeline(self.converter, self.chunker, self.embeddings, markdown_store=store)

        result = await pipeline.ingest(b"document", chunk_mapper=lambda chunk: {"pages": list(chunk.page_numbers)})

        self.assertEqual(result.chunks[0].page_numbers, (2, 3))
        self.assertEqual(store.documents, [{"pages": [2, 3]}])

    async def test_empty_chunks_still_store_metadata_without_embedding_or_markdown(self) -> None:
        """Persist document metadata even when conversion yields no chunks."""
        self.chunker.chunk.return_value = []
        result = await self._ingest()
        self.assertEqual(result, ChunkResult([], self.metadata))
        self.embeddings.generate.assert_not_called()
        self.markdown_store.store_markdown.assert_not_called()
        self.metadata_store.store_metadata.assert_awaited_once_with(self.metadata, metadata_mapper=self.metadata_mapper)

    async def test_ingest_without_stores_fails_before_processing(self) -> None:
        """Do not silently fall back to chunking when persistence is requested."""
        pipeline = Pipeline(self.converter, self.chunker, self.embeddings)
        with self.assertRaisesRegex(ValueError, "at least one configured store"):
            await pipeline.ingest(b"document")
        self.converter.convert.assert_not_called()

    async def test_missing_mappers_fail_before_processing_or_writes(self) -> None:
        """Require a callable mapper for every configured storage role."""
        with self.assertRaisesRegex(TypeError, "chunk_mapper"):
            await self.pipeline.ingest(b"document")
        with self.assertRaisesRegex(TypeError, "metadata_mapper"):
            await self.pipeline.ingest(b"document", chunk_mapper=self.chunk_mapper)
        with self.assertRaisesRegex(TypeError, "chunk_mapper"):
            await self.pipeline.ingest(b"document", metadata_mapper=self.metadata_mapper)
        self.converter.convert.assert_not_called()
        self.metadata_store.store_metadata.assert_not_called()
        self.markdown_store.store_markdown.assert_not_called()

    async def test_mapper_without_matching_store_fails_before_processing(self) -> None:
        """Reject ignored configuration rather than silently dropping a mapper."""
        metadata_only = Pipeline(self.converter, self.chunker, self.embeddings, metadata_store=self.metadata_store)
        with self.assertRaisesRegex(ValueError, "configured markdown_store"):
            await metadata_only.ingest(b"document", chunk_mapper=self.chunk_mapper, metadata_mapper=self.metadata_mapper)
        markdown_only = Pipeline(self.converter, self.chunker, self.embeddings, markdown_store=self.markdown_store)
        with self.assertRaisesRegex(ValueError, "configured metadata_store"):
            await markdown_only.ingest(b"document", chunk_mapper=self.chunk_mapper, metadata_mapper=self.metadata_mapper)
        self.converter.convert.assert_not_called()

    async def test_processing_failures_prevent_all_storage(self) -> None:
        """Propagate conversion, chunking, and embedding errors unchanged."""
        for component in (self.converter.convert, self.chunker.chunk, self.embeddings.generate):
            with self.subTest(component=component):
                error = RuntimeError("processing failed")
                component.side_effect = error
                with self.assertRaises(RuntimeError) as raised:
                    await self._ingest()
                self.assertIs(raised.exception, error)
                self.metadata_store.store_metadata.assert_not_called()
                self.markdown_store.store_markdown.assert_not_called()
                component.side_effect = None

    async def test_embedding_count_mismatch_prevents_all_storage(self) -> None:
        """Never persist chunks without correctly aligned embeddings."""
        self.embeddings.generate.return_value = []
        with self.assertRaisesRegex(RuntimeError, "expected 1 embeddings"):
            await self._ingest()
        self.metadata_store.store_metadata.assert_not_called()
        self.markdown_store.store_markdown.assert_not_called()

    async def test_metadata_failure_prevents_markdown_write(self) -> None:
        """Preserve write ordering and propagate metadata provider errors."""
        error = RuntimeError("metadata unavailable")
        self.metadata_store.store_metadata.side_effect = error
        with self.assertRaises(RuntimeError) as raised:
            await self._ingest()
        self.assertIs(raised.exception, error)
        self.markdown_store.store_markdown.assert_not_called()

    async def test_markdown_failure_propagates_after_metadata_write(self) -> None:
        """Do not return a successful result after a partially completed write."""
        error = RuntimeError("Markdown unavailable")
        self.markdown_store.store_markdown.side_effect = error
        with self.assertRaises(RuntimeError) as raised:
            await self._ingest()
        self.assertIs(raised.exception, error)
        self.metadata_store.store_metadata.assert_awaited_once()

    async def test_mapper_failure_propagates_through_real_storage_contracts(self) -> None:
        """Retain earlier metadata when chunk mapping fails in a later call."""
        markdown_store = RecordingStore()
        metadata_store = RecordingStore()
        pipeline = Pipeline(self.converter, self.chunker, self.embeddings, markdown_store=markdown_store, metadata_store=metadata_store)
        error = ValueError("chunk mapping failed")
        with self.assertRaises(ValueError) as raised:
            await pipeline.ingest(b"document", chunk_mapper=Mock(side_effect=error), metadata_mapper=lambda metadata: {"id": "document", "details": metadata})
        self.assertIs(raised.exception, error)
        self.assertEqual(markdown_store.documents, [])
        self.assertEqual(metadata_store.documents, [{"id": "document", "details": self.metadata}])

    async def test_repeated_ingestion_uses_fresh_results_and_callbacks(self) -> None:
        """Avoid retaining prior document results or per-call mapper callbacks."""
        first = await self._ingest()
        self.converter.convert.return_value = ("second", {"title": "Second"})
        self.chunker.chunk.return_value = [Chunk("second")]
        self.embeddings.generate.return_value = [[3.0, 4.0]]
        chunk_mapper = Mock()
        metadata_mapper = Mock()
        second = await self.pipeline.ingest(b"second", chunk_mapper=chunk_mapper, metadata_mapper=metadata_mapper)
        self.assertEqual(first.metadata, {"title": "Example", "approved": False})
        self.assertEqual(second, ChunkResult([EmbeddedChunk("second", "second", [3.0, 4.0])], {"title": "Second"}))
        self.metadata_store.store_metadata.assert_awaited_with(second.metadata, metadata_mapper=metadata_mapper)
        self.markdown_store.store_markdown.assert_awaited_with(second.chunks, chunk_mapper=chunk_mapper)


if __name__ == "__main__":
    unittest.main()
