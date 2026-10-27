"""Tests for document conversion, chunking, and embedding orchestration."""

import inspect
import unittest
from dataclasses import asdict
from typing import get_type_hints
from unittest.mock import AsyncMock, Mock, call

from ingestra.chunker import BaseChunker, Chunk, MarkdownTokenChunker
from ingestra.converter import BaseConverter
from ingestra.embeddings import BaseEmbeddings
from ingestra.pipeline import ChunkResult, EmbeddedChunk, Pipeline


class PipelineModelTests(unittest.TestCase):
    def test_result_contains_embedded_chunks_and_document_metadata(self) -> None:
        result = ChunkResult(
            chunks=[EmbeddedChunk("source", "# Heading\nsource", [1.0, 2.0])],
            metadata={"approved": False, "total": 0},
        )

        self.assertEqual(
            asdict(result),
            {
                "chunks": [
                    {
                        "original_text": "source",
                        "embedding_text": "# Heading\nsource",
                        "embedding": [1.0, 2.0],
                        "page_numbers": (),
                    }
                ],
                "metadata": {"approved": False, "total": 0},
            },
        )

    def test_public_annotations_describe_the_result_shape(self) -> None:
        self.assertTrue(inspect.iscoroutinefunction(Pipeline.convert))
        self.assertEqual(get_type_hints(Pipeline.convert), {"data": bytes, "return": tuple[str, dict[str, object]]})
        self.assertTrue(inspect.iscoroutinefunction(Pipeline.chunk))
        self.assertEqual(
            get_type_hints(Pipeline.chunk),
            {"markdown": str, "return": list[EmbeddedChunk]},
        )
        self.assertEqual(
            get_type_hints(ChunkResult),
            {"chunks": list[EmbeddedChunk], "metadata": dict[str, object]},
        )
        self.assertEqual(
            get_type_hints(EmbeddedChunk),
            {
                "original_text": str,
                "embedding_text": str,
                "embedding": list[float],
                "page_numbers": tuple[int, ...],
            },
        )

    def test_embedded_chunk_preserves_page_numbers_and_constructor_defaults(self) -> None:
        """Support source pages without changing existing positional arguments."""
        self.assertEqual(EmbeddedChunk("source", "source", [1.0]).page_numbers, ())
        chunk = EmbeddedChunk("source", "source", [1.0], page_numbers=(2, 3))
        self.assertEqual(chunk.page_numbers, (2, 3))


class PipelineTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        self.metadata = {
            "approved": False,
            "total": 0,
            "customer": {"name": "Example"},
        }
        self.markdown = "# Zulu\n\nFirst.\n\n# Alpha\n\nSecond."
        self.chunks = [
            Chunk("first source", "# Zulu\n\nfirst source", 8, (2,)),
            Chunk("second source", "# Alpha\n\nsecond source", 9, (3,)),
        ]
        self.vectors = [[1.0, 2.0], [3.0, 4.0]]
        self.converter = Mock(spec=BaseConverter)
        self.converter.convert = AsyncMock(
            return_value=(self.markdown, self.metadata)
        )
        self.chunker = Mock(spec=BaseChunker)
        self.chunker.chunk.return_value = self.chunks
        self.embeddings = Mock(spec=BaseEmbeddings)
        self.embeddings.generate = AsyncMock(return_value=self.vectors)
        self.pipeline = Pipeline(
            self.converter, self.chunker, self.embeddings
        )

    async def test_given_bytes_when_convert_then_returns_markdown_and_metadata_only(self) -> None:
        """Return converter output without running subsequent stages."""
        result = await self.pipeline.convert(b"document")

        self.assertEqual(result, (self.markdown, self.metadata))
        self.assertIs(result[1], self.metadata)
        self.converter.convert.assert_awaited_once_with(b"document")
        self.chunker.chunk.assert_not_called()
        self.embeddings.generate.assert_not_called()

    async def test_given_markdown_when_chunk_then_returns_list_without_conversion(self) -> None:
        """Allow caller-provided Markdown without invoking the converter."""
        result = await self.pipeline.chunk(self.markdown)

        self.assertEqual(len(result), 2)
        self.assertIsInstance(result, list)
        self.chunker.chunk.assert_called_once_with(self.markdown)
        self.converter.convert.assert_not_called()

    async def test_executes_stages_in_order_and_preserves_alignment(self) -> None:
        stages = Mock()
        stages.attach_mock(self.converter.convert, "convert")
        stages.attach_mock(self.chunker.chunk, "chunk")
        stages.attach_mock(self.embeddings.generate, "generate")
        data = b"\x00\xffdocument"

        markdown, metadata = await self.pipeline.convert(data)
        result = await self.pipeline.chunk(markdown)

        self.assertEqual(
            stages.mock_calls,
            [
                call.convert(data),
                call.chunk(self.markdown),
                call.generate([chunk.embedding_text for chunk in self.chunks]),
            ],
        )
        self.converter.convert.assert_awaited_once_with(data)
        self.embeddings.generate.assert_awaited_once_with(
            [chunk.embedding_text for chunk in self.chunks]
        )
        self.assertEqual(
            result,
            [
                EmbeddedChunk("first source", "# Zulu\n\nfirst source", [1.0, 2.0], page_numbers=(2,)),
                EmbeddedChunk("second source", "# Alpha\n\nsecond source", [3.0, 4.0], page_numbers=(3,)),
            ],
        )
        self.assertIs(metadata, self.metadata)

    async def test_chunks_without_embedding_text_embed_the_original_text(self) -> None:
        """Retain the generic interface fallback for custom chunkers."""
        self.chunker.chunk.return_value = [
            Chunk("  first source\n"),
            self.chunks[1],
        ]

        result = await self.pipeline.chunk(self.markdown)

        self.embeddings.generate.assert_awaited_once_with(
            ["  first source\n", "# Alpha\n\nsecond source"]
        )
        self.assertEqual(
            result[0],
            EmbeddedChunk("  first source\n", "  first source\n", [1.0, 2.0]),
        )
        self.assertEqual(
            self.chunker.chunk.return_value[0],
            Chunk("  first source\n"),
        )

    async def test_multi_page_and_unknown_page_numbers_remain_aligned(self) -> None:
        """Retain page tuples for fallback text and chunks with unknown pages."""
        self.chunker.chunk.return_value = [
            Chunk("first source", page_numbers=(2, 3)),
            Chunk("second source", "second embedding"),
        ]

        result = await self.pipeline.chunk(self.markdown)

        self.assertEqual([chunk.page_numbers for chunk in result], [(2, 3), ()])
        self.embeddings.generate.assert_awaited_once_with(["first source", "second embedding"])

    async def test_empty_chunks_skip_embeddings(self) -> None:
        self.chunker.chunk.return_value = []

        result = await self.pipeline.chunk(self.markdown)

        self.assertEqual(result, [])
        self.embeddings.generate.assert_not_called()

    async def test_empty_bytes_are_forwarded_to_the_converter(self) -> None:
        await self.pipeline.convert(b"")

        self.converter.convert.assert_awaited_once_with(b"")

    async def test_rejects_non_bytes_before_running_any_stage(self) -> None:
        for data in (None, "document", bytearray(b"document"), memoryview(b"x"), 1):
            with self.subTest(data=data):
                with self.assertRaisesRegex(TypeError, "data must be bytes"):
                    await self.pipeline.convert(data)

        self.converter.convert.assert_not_called()
        self.chunker.chunk.assert_not_called()
        self.embeddings.generate.assert_not_called()

    async def test_given_non_string_when_chunk_then_rejects_before_processing(self) -> None:
        """Reject non-Markdown inputs without invoking any component."""
        for markdown in (None, b"document", bytearray(b"document"), memoryview(b"x"), 1):
            with self.subTest(markdown=markdown):
                with self.assertRaisesRegex(TypeError, "markdown must be a string"):
                    await self.pipeline.chunk(markdown)

        self.converter.convert.assert_not_called()
        self.chunker.chunk.assert_not_called()
        self.embeddings.generate.assert_not_called()

    async def test_rejects_missing_or_extra_embeddings(self) -> None:
        for vectors in ([], [[1.0]], [[1.0], [2.0], [3.0]]):
            with self.subTest(vectors=vectors):
                self.embeddings.generate.return_value = vectors

                with self.assertRaisesRegex(
                    RuntimeError, "expected 2 embeddings"
                ):
                    await self.pipeline.chunk(self.markdown)

    async def test_converter_errors_propagate_without_running_later_stages(
        self,
    ) -> None:
        error = ValueError("unsupported format")
        self.converter.convert.side_effect = error

        with self.assertRaises(ValueError) as caught:
            await self.pipeline.convert(b"document")

        self.assertIs(caught.exception, error)
        self.chunker.chunk.assert_not_called()
        self.embeddings.generate.assert_not_called()

    async def test_chunker_errors_propagate_without_embedding(self) -> None:
        error = ValueError("token budget too small")
        self.chunker.chunk.side_effect = error

        with self.assertRaises(ValueError) as caught:
            await self.pipeline.chunk(self.markdown)

        self.assertIs(caught.exception, error)
        self.embeddings.generate.assert_not_called()

    async def test_embedding_errors_propagate_unchanged(self) -> None:
        error = RuntimeError("embedding provider unavailable")
        self.embeddings.generate.side_effect = error

        with self.assertRaises(RuntimeError) as caught:
            await self.pipeline.chunk(self.markdown)

        self.assertIs(caught.exception, error)

    async def test_repeated_calls_do_not_retain_prior_results(self) -> None:
        first = await self.pipeline.chunk(self.markdown)
        self.chunker.chunk.return_value = [Chunk("second source")]
        self.embeddings.generate.return_value = [[5.0]]

        second = await self.pipeline.chunk("second source")

        self.assertEqual(len(first), 2)
        self.assertEqual(
            second,
            [EmbeddedChunk("second source", "second source", [5.0])],
        )

    async def test_real_markdown_token_chunker_preserves_source(self) -> None:
        """Preserve source order and embedding alignment with token chunking."""
        chunker = MarkdownTokenChunker(chunk_size=40, tokenizer=len)
        self.embeddings.generate.side_effect = lambda texts: [
            [float(len(text))] for text in texts
        ]
        pipeline = Pipeline(self.converter, chunker, self.embeddings)

        result = await pipeline.chunk(self.markdown)

        self.assertEqual("".join(chunk.original_text for chunk in result), self.markdown)
        self.assertTrue(result)
        self.embeddings.generate.assert_awaited_once_with([chunk.embedding_text for chunk in result])
        for chunk in result:
            self.assertEqual(chunk.embedding, [float(len(chunk.embedding_text))])

    async def test_real_markdown_token_chunker_preserves_page_numbers(self) -> None:
        """Carry parsed source pages through embedding without altering input."""
        markdown = "<!-- InputPageNumber: 1 -->\n\n| Name | Value |\n| --- | --- |\n"
        markdown += "".join(f"| Item {i} | {i} |\n" for i in range(40))
        markdown += "\n<!-- InputPageNumber: 2 -->\n\n# Next\nBody."
        self.embeddings.generate.side_effect = lambda texts: [[float(len(text))] for text in texts]
        chunker = MarkdownTokenChunker(chunk_size=180, tokenizer=len)
        pipeline = Pipeline(self.converter, chunker, self.embeddings)

        result = await pipeline.chunk(markdown)

        self.assertEqual("".join(chunk.original_text for chunk in result), markdown)
        self.assertEqual([chunk.page_numbers for chunk in result], [chunk.page_numbers for chunk in chunker.chunk(markdown)])
        self.assertEqual({page for chunk in result for page in chunk.page_numbers}, {1, 2})
        self.embeddings.generate.assert_awaited_once_with([chunk.embedding_text for chunk in result])

    async def test_blank_markdown_has_no_chunks_or_embedding_requests(self) -> None:
        pipeline = Pipeline(
            self.converter, MarkdownTokenChunker(chunk_size=40, tokenizer=len), self.embeddings
        )
        for markdown in ("", " \t\r\n"):
            with self.subTest(markdown=markdown):
                result = await pipeline.chunk(markdown)

                self.assertEqual(result, [])

        self.embeddings.generate.assert_not_called()


if __name__ == "__main__":
    unittest.main()
