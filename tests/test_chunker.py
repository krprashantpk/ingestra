"""Tests for the implementation-independent chunker interface."""

import inspect
import subprocess
import sys
import unittest
from dataclasses import FrozenInstanceError, asdict
from typing import get_type_hints
from unittest.mock import patch

from ingestra.chunker import BaseChunker, Chunk, MarkdownTokenChunker


class WhitespaceChunker(BaseChunker):
    def chunk(self, text: str) -> list[Chunk]:
        if not isinstance(text, str):
            raise TypeError("text must be a string")
        return [Chunk(original_text=word) for word in text.split()]


class ChunkModelTests(unittest.TestCase):
    def test_model_has_exactly_the_four_shared_fields(self) -> None:
        self.assertEqual(
            asdict(Chunk(original_text="source")),
            {
                "original_text": "source",
                "embedding_text": None,
                "token_count": None,
                "page_numbers": (),
            },
        )

    def test_model_retains_embedding_and_source_metadata(self) -> None:
        metadata = {
            "original_text": "  source\n",
            "embedding_text": "# Heading\n\n  source\n",
            "token_count": 7,
            "page_numbers": (2, 3),
        }

        chunk = Chunk(
            original_text="  source\n",
            embedding_text="# Heading\n\n  source\n",
            token_count=7,
            page_numbers=(2, 3),
        )

        self.assertEqual(asdict(chunk), metadata)

    def test_model_is_immutable(self) -> None:
        chunk = Chunk(original_text="original")

        with self.assertRaises(FrozenInstanceError):
            setattr(chunk, "original_text", "changed")

    def test_shared_model_has_no_format_specific_aliases(self) -> None:
        """Expose the shared model only under its canonical name."""
        import ingestra.chunker as chunkers
        import ingestra.chunker.markdown as markdown

        for module in (chunkers, markdown):
            with self.subTest(module=module.__name__):
                names = [name for name, value in vars(module).items() if value is Chunk]
                self.assertEqual(names, ["Chunk"])


class ChunkerInterfaceTests(unittest.TestCase):
    def test_base_class_cannot_be_instantiated(self) -> None:
        self.assertTrue(inspect.isabstract(BaseChunker))
        with self.assertRaises(TypeError):
            BaseChunker()

    def test_subclass_must_implement_chunk(self) -> None:
        class IncompleteChunker(BaseChunker):
            pass

        with self.assertRaises(TypeError):
            IncompleteChunker()

    def test_markdown_token_chunker_implements_the_interface(self) -> None:
        """Expose the token implementation through the shared interface."""
        self.assertTrue(issubclass(MarkdownTokenChunker, BaseChunker))
        self.assertFalse(inspect.isabstract(MarkdownTokenChunker))

    def test_custom_chunker_uses_the_shared_model(self) -> None:
        chunker: BaseChunker = WhitespaceChunker()

        chunks = chunker.chunk("first second\nthird")

        self.assertEqual(chunks, [Chunk("first"), Chunk("second"), Chunk("third")])
        self.assertTrue(all(type(chunk) is Chunk for chunk in chunks))

    def test_public_return_annotations_use_the_shared_model(self) -> None:
        for method in (BaseChunker.chunk, MarkdownTokenChunker.chunk):
            with self.subTest(method=method.__qualname__):
                self.assertEqual(get_type_hints(method)["return"], list[Chunk])

    def test_markdown_token_chunker_can_be_used_through_the_interface(self) -> None:
        """Return the shared chunk model with bounded embedding text."""
        chunker: BaseChunker = MarkdownTokenChunker(chunk_size=40, tokenizer=len)
        text = "# Heading\n\n" + "One sentence. " * 20

        chunks = chunker.chunk(text)

        self.assertGreater(len(chunks), 1)
        self.assertTrue(all(type(chunk) is Chunk for chunk in chunks))
        self.assertEqual("".join(chunk.original_text for chunk in chunks), text)
        for chunk in chunks:
            self.assertIsNotNone(chunk.embedding_text)
            self.assertEqual(chunk.token_count, len(chunk.embedding_text))
            self.assertLessEqual(chunk.token_count, 60)

    def test_empty_or_whitespace_only_input_returns_no_chunks(self) -> None:
        for chunker in (
            WhitespaceChunker(),
            MarkdownTokenChunker(chunk_size=40, tokenizer=len),
        ):
            for text in ("", " \t\r\n"):
                with self.subTest(chunker=type(chunker).__name__, text=text):
                    chunks = chunker.chunk(text)
                    self.assertIsInstance(chunks, list)
                    self.assertEqual(chunks, [])

    def test_chunkers_always_return_a_list_in_source_order(self) -> None:
        parts = ["# Zulu\n\n" + "Third. " * 5 + "\n\n", "# Alpha\n\n" + "First. " * 5 + "\n\n", "# Middle\n\n" + "Second. " * 5]
        text = "".join(parts)
        chunks = MarkdownTokenChunker(chunk_size=90, tokenizer=len).chunk(text)
        self.assertIsInstance(chunks, list)
        self.assertEqual("".join(chunk.original_text for chunk in chunks), text)

    def test_existing_markdown_keyword_argument_is_preserved(self) -> None:
        text = "# Heading\n\nBody."

        chunks = MarkdownTokenChunker(chunk_size=100, tokenizer=len).chunk(markdown=text)
        self.assertEqual("".join(chunk.original_text for chunk in chunks), text)


class MarkdownTokenAPITests(unittest.TestCase):
    """Verify the token-only public API and its configuration contract."""

    def test_token_chunker_is_exported_from_both_public_modules(self) -> None:
        """Make the named chunker available at the supported import paths."""
        import ingestra.chunker as chunkers
        from ingestra.chunker.markdown import MarkdownTokenChunker as TokenImplementation

        self.assertIs(chunkers.MarkdownTokenChunker, TokenImplementation)
        self.assertIn("MarkdownTokenChunker", chunkers.__all__)

    def test_character_and_combined_chunkers_have_been_removed(self) -> None:
        """Do not retain aliases or implementations of the removed APIs."""
        import ingestra.chunker as chunkers
        import ingestra.chunker.markdown as markdown

        for name in ("MarkdownCharacterChunker", "MarkdownChunker"):
            with self.subTest(name=name):
                self.assertFalse(hasattr(chunkers, name))
                self.assertFalse(hasattr(markdown, name))
                self.assertNotIn(name, chunkers.__all__)

    def test_constructor_exposes_only_token_settings(self) -> None:
        """Expose one defaulted token-size setting and optional tokenizer injection."""
        token_parameters = inspect.signature(MarkdownTokenChunker).parameters

        self.assertEqual(list(token_parameters), ["chunk_size", "tokenizer"])
        self.assertEqual(token_parameters["chunk_size"].default, 2048)
        self.assertIs(token_parameters["chunk_size"].kind, inspect.Parameter.KEYWORD_ONLY)
        for settings in ({"max_tokens": 100}, {"target_tokens": 100}, {"overlap_tokens": 10}):
            with self.subTest(settings=settings), self.assertRaises(TypeError):
                MarkdownTokenChunker(**settings)

    def test_nonstring_input_is_rejected(self) -> None:
        """Reject invalid source types consistently before parsing."""
        chunker = MarkdownTokenChunker(chunk_size=100, tokenizer=len)
        for source in (None, b"# Heading", 42, ["Body."]):
            with self.subTest(source=source), self.assertRaisesRegex(TypeError, "must be a string"):
                chunker.chunk(source)  # type: ignore[arg-type]

    def test_custom_tokenizer_does_not_require_tiktoken(self) -> None:
        """Avoid loading tiktoken when an explicit tokenizer is supplied."""
        with patch.dict("sys.modules", {"tiktoken": None}):
            chunks = MarkdownTokenChunker(chunk_size=100, tokenizer=len).chunk("Body.")

        self.assertEqual(chunks, [Chunk("Body.", embedding_text="Body.", token_count=5)])

    def test_fresh_import_does_not_eagerly_load_tiktoken(self) -> None:
        """Keep the public API importable without eagerly loading tiktoken."""
        code = (
            "import sys\n"
            "sys.modules['tiktoken'] = None\n"
            "from ingestra.chunker import Chunk, MarkdownTokenChunker\n"
            "chunks = MarkdownTokenChunker(chunk_size=10, tokenizer=len).chunk('Body.')\n"
            "assert len(chunks) == 1 and isinstance(chunks[0], Chunk)\n"
            "assert chunks[0].token_count == 5\n"
        )
        result = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_defaults_match_the_documented_token_size(self) -> None:
        """Default to 2048 tokens without a separate maximum or prose overlap."""
        source = "<!-- InputPageNumber: 3 -->\n\n# Heading\n\n" + "One sentence. " * 80
        default = MarkdownTokenChunker(tokenizer=len)
        explicit = MarkdownTokenChunker(chunk_size=2048, tokenizer=len)
        self.assertEqual(default.chunk(source), explicit.chunk(source))


class MarkdownPageHelperTests(unittest.TestCase):
    """Verify the opt-in helper without changing the chunking input contract."""

    def test_pages_are_joined_with_one_based_markers(self) -> None:
        """Return the exact page-marker format recognized by the chunker."""
        markdown = MarkdownTokenChunker.pages_to_markdown(["First page.", "Second page."])

        self.assertEqual(markdown, "<!-- InputPageNumber: 1 -->\n\nFirst page.\n\n<!-- InputPageNumber: 2 -->\n\nSecond page.")
        chunks = MarkdownTokenChunker(chunk_size=200, tokenizer=len).chunk(markdown)
        self.assertEqual("".join(chunk.original_text for chunk in chunks), markdown)
        self.assertEqual({page for chunk in chunks for page in chunk.page_numbers}, {1, 2})

    def test_single_page_has_no_added_trailing_separator(self) -> None:
        """Only prepend the marker when there is one page."""
        self.assertEqual(MarkdownTokenChunker.pages_to_markdown(["Body."]), "<!-- InputPageNumber: 1 -->\n\nBody.")

    def test_empty_list_returns_empty_string(self) -> None:
        """Do not invent a page when none were supplied."""
        self.assertEqual(MarkdownTokenChunker.pages_to_markdown([]), "")

    def test_page_content_and_empty_page_positions_are_preserved(self) -> None:
        """Keep whitespace, line endings, Unicode, and page order unchanged."""
        pages = [" \r\n# Heading\r\nBody.  \r\n", "", "\u4e2d\u6587\n"]
        original = pages.copy()

        markdown = MarkdownTokenChunker.pages_to_markdown(pages)

        self.assertEqual(markdown, "<!-- InputPageNumber: 1 -->\n\n \r\n# Heading\r\nBody.  \r\n\n\n<!-- InputPageNumber: 2 -->\n\n\n\n<!-- InputPageNumber: 3 -->\n\n\u4e2d\u6587\n")
        self.assertEqual(pages, original)

    def test_helper_is_also_available_on_an_instance(self) -> None:
        """Expose the same stateless conversion through a chunker instance."""
        chunker = MarkdownTokenChunker(chunk_size=100, tokenizer=len)
        self.assertEqual(chunker.pages_to_markdown(["Body."]), "<!-- InputPageNumber: 1 -->\n\nBody.")

    def test_nonlist_input_is_rejected(self) -> None:
        """Reject inputs that could otherwise be mistaken for pages."""
        for pages in (None, "Body.", b"Body.", 42, ("Body.",)):
            with self.subTest(pages=pages), self.assertRaisesRegex(TypeError, "pages must be a list of strings"):
                MarkdownTokenChunker.pages_to_markdown(pages)  # type: ignore[arg-type]

    def test_nonstring_page_is_rejected_with_its_index(self) -> None:
        """Do not silently stringify invalid page contents."""
        for page in (None, 42, b"Body.", ["Body."]):
            with self.subTest(page=page), self.assertRaisesRegex(TypeError, r"pages\[1\] must be a string"):
                MarkdownTokenChunker.pages_to_markdown(["Valid.", page])  # type: ignore[list-item]


if __name__ == "__main__":
    unittest.main()
