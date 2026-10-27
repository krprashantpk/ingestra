"""Tests for independent Markdown and metadata storage contracts."""

import inspect
import unittest
from unittest.mock import Mock

from ingestra.pipeline import EmbeddedChunk
from ingestra.store import BaseMarkdownStore, BaseMetadataStore
from ingestra.store.markdown.base import BaseMarkdownStore as MarkdownBase
from ingestra.store.metadata.base import BaseMetadataStore as MetadataBase


class CapturingStore(BaseMarkdownStore, BaseMetadataStore):
    """Capture documents using the same hook required by concrete providers."""

    def __init__(self) -> None:
        """Initialize captured write operations."""
        self.writes: list[list[dict[str, object]]] = []

    async def _store_documents(self, documents: list[dict[str, object]]) -> None:
        """Capture a mapped write operation."""
        self.writes.append(documents)


class StoreContractTests(unittest.IsolatedAsyncioTestCase):
    """Verify provider-independent mapping and error behavior."""

    def setUp(self) -> None:
        """Create a provider and ordered embedded chunks."""
        self.store = CapturingStore()
        self.chunks = [EmbeddedChunk("# One", "One", [1.0, 2.0]), EmbeddedChunk("# Two", "Two", [3.0, 4.0])]

    def test_exports_and_abstract_contracts(self) -> None:
        """Keep both public bases abstract and independently importable."""
        self.assertIs(BaseMarkdownStore, MarkdownBase)
        self.assertIs(BaseMetadataStore, MetadataBase)
        for base in (BaseMarkdownStore, BaseMetadataStore):
            with self.subTest(base=base):
                self.assertTrue(inspect.isabstract(base))
                self.assertRaises(TypeError, base)
        self.assertTrue(inspect.iscoroutinefunction(BaseMarkdownStore.store_markdown))
        self.assertTrue(inspect.iscoroutinefunction(BaseMetadataStore.store_metadata))

    async def test_maps_ordered_chunks_and_copies_reused_dictionaries(self) -> None:
        """Snapshot each mapped chunk before the mapper reuses its buffer."""
        shared: dict[str, object] = {"nested": {"values": []}}

        def mapper(chunk: EmbeddedChunk) -> dict[str, object]:
            """Return a reused mutable document for each source chunk."""
            shared["text"] = chunk.original_text
            shared["vector"] = chunk.embedding
            return shared

        await self.store.store_markdown(tuple(self.chunks), chunk_mapper=mapper)
        shared.clear()
        self.chunks[0].embedding.append(99.0)
        self.assertEqual([document["text"] for document in self.store.writes[0]], ["# One", "# Two"])
        self.assertEqual(self.store.writes[0][0]["vector"], [1.0, 2.0])
        self.assertIsNot(self.store.writes[0][0]["nested"], self.store.writes[0][1]["nested"])

    async def test_maps_metadata_once_and_copies_nested_output(self) -> None:
        """Store metadata independently and retain a deep snapshot."""
        metadata: dict[str, object] = {"nested": {"value": False}}
        mapped: dict[str, object] = {"key": "document-1", "metadata": metadata}
        mapper = Mock(return_value=mapped)
        await self.store.store_metadata(metadata, metadata_mapper=mapper)
        mapper.assert_called_once_with(metadata)
        metadata.clear()
        mapped.clear()
        self.assertEqual(self.store.writes, [[{"key": "document-1", "metadata": {"nested": {"value": False}}}]])

    async def test_empty_chunks_do_not_prevent_independent_empty_metadata_write(self) -> None:
        """Skip empty chunk operations while still storing mapped empty metadata."""
        chunk_mapper = Mock()
        await self.store.store_markdown([], chunk_mapper=chunk_mapper)
        await self.store.store_metadata({}, metadata_mapper=lambda metadata: {"key": "empty"})
        chunk_mapper.assert_not_called()
        self.assertEqual(self.store.writes, [[{"key": "empty"}]])

    async def test_mapper_failure_prevents_all_writes_for_that_operation(self) -> None:
        """Propagate failures before persisting any partially mapped chunk list."""
        error = ValueError("mapping failed")
        mapper = Mock(side_effect=[{"key": "one"}, error])
        with self.assertRaises(ValueError) as raised:
            await self.store.store_markdown(self.chunks, chunk_mapper=mapper)
        self.assertIs(raised.exception, error)
        self.assertEqual(self.store.writes, [])

    async def test_rejects_non_dictionary_mapper_results(self) -> None:
        """Reject malformed callback output rather than performing a write."""
        mapper = Mock(return_value=None)
        with self.assertRaisesRegex(TypeError, "dictionary"):
            await self.store.store_markdown(self.chunks, chunk_mapper=mapper)
        with self.assertRaisesRegex(TypeError, "dictionary"):
            await self.store.store_metadata({}, metadata_mapper=mapper)
        self.assertEqual(self.store.writes, [])

    async def test_metadata_mapper_errors_propagate(self) -> None:
        """Retain the original error without persisting metadata."""
        error = RuntimeError("metadata mapping failed")
        with self.assertRaises(RuntimeError) as raised:
            await self.store.store_metadata({}, metadata_mapper=Mock(side_effect=error))
        self.assertIs(raised.exception, error)
        self.assertEqual(self.store.writes, [])


if __name__ == "__main__":
    unittest.main()
