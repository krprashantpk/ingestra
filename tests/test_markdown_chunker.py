"""Tests for local Markdown chunking without Azure requests."""

import random
import unittest
from dataclasses import asdict
from pathlib import Path
from unittest.mock import Mock, patch
from xml.etree import ElementTree

from ingestra.chunker import Chunk, MarkdownTokenChunker


class MarkdownTokenChunkerTests(unittest.TestCase):
    """Verify token-size goals, natural-boundary flexibility, and source contracts."""

    def test_given_nearby_sentence_end_when_packing_then_allows_a_small_overrun(self) -> None:
        """Finish a sentence when that boundary is closer than an early cut."""
        first, second, third = "a" * 68 + ". ", "b" * 38 + ". ", "c" * 38 + ". "
        text = first + second + third

        chunks = MarkdownTokenChunker(chunk_size=100, tokenizer=len).chunk(text)

        self.assertEqual(chunks[0].original_text, first + second)
        self.assertEqual(chunks[0].token_count, 110)
        self.assertEqual("".join(chunk.original_text for chunk in chunks), text)

    def test_given_nearby_table_row_when_packing_then_keeps_the_row_complete(self) -> None:
        """Allow a closer complete row instead of enforcing a character-like ceiling."""
        header = "| Name | Value |\n| --- | --- |\n"
        rows = [f"| Item {number} | Description {number} |\n" for number in range(8)]
        size = len(header + rows[0] + rows[1]) - 5
        text = header + "".join(rows)

        chunks = MarkdownTokenChunker(chunk_size=size, tokenizer=len).chunk(text)

        self.assertEqual(chunks[0].original_text, header + rows[0] + rows[1])
        self.assertEqual(chunks[0].token_count, size + 5)
        self.assertEqual("".join(chunk.original_text for chunk in chunks), text)
        for chunk in chunks:
            self.assertIsNotNone(chunk.embedding_text)
            self.assertIn(header, chunk.embedding_text)

    def test_given_prose_when_packing_then_does_not_repeat_previous_sentences(self) -> None:
        """Keep prose overlap removed while retaining exact source slices."""
        text = "".join(f"Sentence number {number} ends here. " for number in range(40))

        chunks = MarkdownTokenChunker(chunk_size=100, tokenizer=len).chunk(text)

        self.assertGreater(len(chunks), 1)
        self.assertTrue(all(chunk.embedding_text == chunk.original_text for chunk in chunks))
        self.assertEqual("".join(chunk.original_text for chunk in chunks), text)

    def test_given_oversized_sentence_when_packing_then_descends_to_words(self) -> None:
        """Split an individually oversized sentence without splitting ordinary words."""
        text = " ".join(f"word{number}" for number in range(100)) + "."

        chunks = MarkdownTokenChunker(chunk_size=80, tokenizer=len).chunk(text)

        self.assertGreater(len(chunks), 1)
        self.assertEqual("".join(chunk.original_text for chunk in chunks), text)
        self.assertTrue(all(chunk.original_text.endswith(" ") for chunk in chunks[:-1]))

    def test_given_document_with_mixed_blocks_when_it_fits_then_returns_one_chunk(self) -> None:
        """Keep a fitting document whole across headings and structural blocks."""
        text = "---\ntitle: Example\n---\n\n# Guide\n\nIntroduction.\n\n"
        text += "## Code\n\n```python\nprint(1)\n```\n\n"
        text += "## Table\n\n| Name |\n| --- |\n| Value |\n"

        chunks = MarkdownTokenChunker(chunk_size=len(text), tokenizer=len).chunk(text)

        self.assertEqual(chunks, [Chunk(text, embedding_text=text, token_count=len(text))])

    def test_given_small_sections_when_document_is_oversized_then_packs_across_headings(self) -> None:
        """Treat section boundaries as preferred splits rather than mandatory chunks."""
        parts = [f"## Section {number}\n\nBody {number}.\n\n" for number in range(8)]
        text = "".join(parts)

        chunks = MarkdownTokenChunker(chunk_size=100, tokenizer=len).chunk(text)

        self.assertLess(len(chunks), len(parts))
        self.assertIn(parts[0] + parts[1], chunks[0].original_text)
        self.assertEqual("".join(chunk.original_text for chunk in chunks), text)
        self.assertTrue(all(chunk.embedding_text is not None and chunk.token_count == len(chunk.embedding_text) <= 100 for chunk in chunks))

    def test_given_nested_sections_when_parent_is_oversized_then_fills_across_children(self) -> None:
        """Refine child sections rather than leaving substantially underfilled chunks."""
        parts = [f"## Child {number}\n\n" + "First sentence. Second sentence.\n\n" * 2 for number in range(4)]
        text = "# Parent\n\n" + "".join(parts)

        chunks = MarkdownTokenChunker(chunk_size=130, tokenizer=len).chunk(text)

        self.assertLess(len(chunks), len(parts))
        self.assertEqual("".join(chunk.original_text for chunk in chunks), text)
        self.assertTrue(all(chunk.embedding_text is not None and "# Parent" in chunk.embedding_text for chunk in chunks))
        self.assertTrue(all(chunk.token_count is not None and 110 <= chunk.token_count <= 150 for chunk in chunks[:-1]))

    def test_given_mixed_blocks_when_document_is_oversized_then_packs_complete_blocks(self) -> None:
        """Combine adjacent prose, code, and tables without fragmenting fitting blocks."""
        block = "Paragraph.\n\n```text\nExample\n```\n\n| Key |\n| --- |\n| A |\n\n"
        text = block * 6

        chunks = MarkdownTokenChunker(chunk_size=130, tokenizer=len).chunk(text)

        self.assertIn(block, chunks[0].original_text)
        self.assertEqual("".join(chunk.original_text for chunk in chunks), text)
        self.assertTrue(all(chunk.original_text.count("```") % 2 == 0 for chunk in chunks))
        self.assertTrue(all(chunk.embedding_text is not None and chunk.token_count == len(chunk.embedding_text) <= 150 for chunk in chunks))

    def test_given_document_under_2028_tokens_when_chunking_then_returns_one_chunk_with_pages(self) -> None:
        """Measure the requested single-chunk behavior with the real tokenizer."""
        import tiktoken

        text = "<!-- InputPageNumber: 1 -->\n\n# Guide\n\nIntroduction.\n\n"
        text += "\n\n".join(f"## Section {number}\n\nA short explanation of topic {number}." for number in range(12))
        text += "\n\n<!-- InputPageNumber: 2 -->\n\n```markdown\n<!-- InputPageNumber: 99 -->\n```\n"
        token_count = len(tiktoken.get_encoding("cl100k_base").encode_ordinary(text))
        self.assertLess(token_count, 2028)

        chunks = MarkdownTokenChunker(chunk_size=2028).chunk(text)

        self.assertEqual(chunks, [Chunk(text, embedding_text=text, token_count=token_count, page_numbers=(1, 2))])

    def test_given_many_small_sections_when_packed_then_approaches_2028_tokens(self) -> None:
        """Pack short sections within 128 tokens of the target except for the final chunk."""
        import tiktoken

        text = "# Manual\n\n" + "".join(f"## Topic {number}\n\n" + "A short explanation gives useful context for this topic. " * 3 + "\n\n" for number in range(200))
        encoding = tiktoken.get_encoding("cl100k_base")

        chunks = MarkdownTokenChunker(chunk_size=2028).chunk(text)

        self.assertGreater(len(chunks), 1)
        self.assertEqual("".join(chunk.original_text for chunk in chunks), text)
        self.assertTrue(all(chunk.embedding_text is not None and chunk.token_count == len(encoding.encode_ordinary(chunk.embedding_text)) <= 2048 for chunk in chunks))
        self.assertTrue(all(chunk.token_count is not None and chunk.token_count >= 1900 for chunk in chunks[:-1]))

    def test_given_document_over_2048_characters_when_tokens_fit_default_then_returns_one_chunk(self) -> None:
        """Use tokens rather than characters for the default size goal."""
        import tiktoken

        text = "Regular English words make a short sentence. " * 100
        tokens = len(tiktoken.get_encoding("cl100k_base").encode_ordinary(text))
        self.assertGreater(len(text), 2048)
        self.assertLess(tokens, 2048)

        chunks = MarkdownTokenChunker().chunk(text)

        self.assertEqual(chunks, [Chunk(text, embedding_text=text, token_count=tokens)])

    def test_given_nonmonotonic_token_prefix_when_document_fits_then_keeps_it_whole(self) -> None:
        """Check the complete input before relying on approximate prefix probing."""
        import tiktoken

        text = "\n 12345 tokenization tokenization ``` a ``` sentence a \U0001f642   tokenization extraordinary"
        encoding = tiktoken.get_encoding("cl100k_base")
        tokens = len(encoding.encode_ordinary(text))

        chunks = MarkdownTokenChunker(chunk_size=tokens).chunk(text)

        self.assertEqual(chunks, [Chunk(text, embedding_text=text, token_count=tokens)])

    def test_given_large_unbroken_text_when_splitting_then_measures_the_full_input_only_once(self) -> None:
        """Bound subsequent prefix measurements instead of retokenizing large suffixes."""
        text = "x" * 32768
        measured_lengths: list[int] = []

        def count(value: str) -> int:
            """Record each measured input length and return a deterministic count."""
            measured_lengths.append(len(value))
            return len(value)

        chunks = MarkdownTokenChunker(chunk_size=128, tokenizer=count).chunk(text)

        self.assertEqual("".join(chunk.original_text for chunk in chunks), text)
        self.assertEqual(measured_lengths.count(len(text)), 1)
        self.assertLessEqual(max(length for length in measured_lengths if length != len(text)), 256)

    def test_chunk_model_has_only_the_four_shared_fields(self) -> None:
        """Retain the common result shape and page attribution."""
        text = "<!-- InputPageNumber: 3 -->\n\n# Section\n\nBody."
        chunks = MarkdownTokenChunker(chunk_size=100, tokenizer=len).chunk(text)

        self.assertEqual("".join(chunk.original_text for chunk in chunks), text)
        self.assertEqual({page for chunk in chunks for page in chunk.page_numbers}, {3})
        for chunk in chunks:
            self.assertEqual(set(asdict(chunk)), {"original_text", "embedding_text", "token_count", "page_numbers"})

    def test_instances_do_not_retain_document_state(self) -> None:
        """Do not leak headings or page context into the next document."""
        chunker = MarkdownTokenChunker(chunk_size=100, tokenizer=len)
        chunker.chunk("<!-- InputPageNumber: 3 -->\n\n# First\nBody.")
        self.assertEqual(chunker.chunk("Next."), [Chunk("Next.", embedding_text="Next.", token_count=5)])

    def test_shorter_or_different_fence_does_not_close_code(self) -> None:
        """Keep mismatched fences inside a code block that fits the budget."""
        code = "````text\n```\n~~~\n# Still code\n\n````\n\n"
        text = code + "After. " * 30
        chunks = MarkdownTokenChunker(chunk_size=100, tokenizer=len).chunk(text)
        self.assertTrue(chunks[0].original_text.startswith(code))
        self.assertEqual("".join(chunk.original_text for chunk in chunks), text)
        self.assertTrue(all("# Still code" not in chunk.embedding_text for chunk in chunks if "# Still code" not in chunk.original_text))

    def test_setext_headings_start_separate_sections(self) -> None:
        """Prefer underlined section boundaries when the document cannot fit."""
        parts = ["Introduction.\n\n", "Title\n=====\n\n" + "Body. " * 10 + "\n\n", "Section\n---\n" + "More. " * 10]
        chunks = MarkdownTokenChunker(chunk_size=100, tokenizer=len).chunk("".join(parts))
        self.assertEqual("".join(chunk.original_text for chunk in chunks), "".join(parts))
        self.assertTrue(any("# Title" in chunk.embedding_text and "## Section" in chunk.embedding_text for chunk in chunks[1:]))

    def test_heading_only_document_retains_all_source_text(self) -> None:
        """Keep consecutive headings even when no body block follows them."""
        text = "# Title\n\n## Subtitle\n"
        chunks = MarkdownTokenChunker(chunk_size=100, tokenizer=len).chunk(text)
        self.assertEqual("".join(chunk.original_text for chunk in chunks), text)

    def test_given_small_structured_block_when_packing_then_keeps_it_complete(self) -> None:
        """Keep a small complete block intact while filling toward the size goal."""
        for block in (
            "```python\n\nprint(1)\n```\n\n",
            "<table><tr><td>Value</td></tr></table>\n\n",
            "<figure>\n<figcaption>Caption</figcaption>\n</figure>\n\n",
            "---\ntitle: Example\n---\n\n",
        ):
            with self.subTest(block=block):
                text = block + "After. " * 100
                chunks = MarkdownTokenChunker(chunk_size=200, tokenizer=len).chunk(text)
                self.assertTrue(chunks[0].original_text.startswith(block))
                self.assertEqual("".join(chunk.original_text for chunk in chunks), text)
                self.assertTrue(all(chunk.token_count is not None and chunk.token_count <= 220 for chunk in chunks))

    def test_token_mode_splits_oversized_blocks_without_losing_source(self) -> None:
        for text in (
            "word " * 200,
            "```python\n" + "print(1)\n" * 200 + "```\n",
            "<table><tr><th>Name</th></tr>"
            + "<tr><td>Value</td></tr>" * 200
            + "</table>",
            "<!-- unclosed\n" + "comment " * 200,
        ):
            with self.subTest(kind=text[:20]):
                chunks = MarkdownTokenChunker(chunk_size=100, tokenizer=len).chunk(text)
                self.assertGreater(len(chunks), 1)
                self.assertEqual("".join(c.original_text for c in chunks), text)
                for chunk in chunks:
                    self.assertIsNotNone(chunk.embedding_text)
                    self.assertTrue(chunk.original_text)
                    self.assertLessEqual(chunk.token_count, 200)
                    self.assertEqual(chunk.token_count, len(chunk.embedding_text))

    def test_cu_sample_obeys_real_embedding_token_limit(self) -> None:
        sample = Path(__file__).resolve().parents[1] / "experiment" / "cu_llm_input.md"
        if not sample.exists():
            self.skipTest("Local CU sample is not distributed with the package")
        import tiktoken

        encoding = tiktoken.get_encoding("cl100k_base")
        text = sample.read_text(encoding="utf-8")
        for maximum in (64, 128, 256, 1024):
            with self.subTest(maximum=maximum), patch(
                "ingestra.chunker._token.logger.warning"
            ):
                chunks = MarkdownTokenChunker(chunk_size=maximum).chunk(text)
                self.assertEqual("".join(c.original_text for c in chunks), text)
                self.assertEqual(
                    {page for c in chunks for page in c.page_numbers}, set(range(1, 78))
                )
                for chunk in chunks:
                    self.assertTrue(chunk.original_text)
                    self.assertTrue(chunk.embedding_text)
                    count = len(encoding.encode_ordinary(chunk.embedding_text))
                    self.assertEqual(chunk.token_count, count)
                    self.assertLessEqual(count, maximum * 2)

    def test_saved_cu_fixture_preserves_source_pages_and_token_budget(self) -> None:
        """Exercise the saved 18-page document with the inspection budgets."""
        import tiktoken

        sample = Path(__file__).parent / "chunkers" / "markdowns" / "redp5110_sampled.md"
        if not sample.is_file():
            self.skipTest("Original 18-page CU fixture is not distributed with the repository")
        text = sample.read_bytes().decode("utf-8")
        encoding = tiktoken.get_encoding("cl100k_base")
        chunks = MarkdownTokenChunker(chunk_size=1024).chunk(text)

        self.assertGreater(len(chunks), 1)
        self.assertEqual("".join(chunk.original_text for chunk in chunks), text)
        self.assertEqual({page for chunk in chunks for page in chunk.page_numbers}, set(range(1, 19)))
        for chunk in chunks:
            self.assertTrue(chunk.original_text)
            self.assertIsNotNone(chunk.embedding_text)
            self.assertEqual(chunk.token_count, len(encoding.encode_ordinary(chunk.embedding_text)))
            self.assertLessEqual(chunk.token_count, 2048)

    def chunk(self, text: str) -> list[Chunk]:
        """Chunk structural fixtures with deterministic counts and bounded natural overruns.

        Args:
            text: Markdown used by a structural regression test.

        Returns:
            Chunks whose source text and measured embedding sizes were checked.
        """
        chunks = MarkdownTokenChunker(chunk_size=180, tokenizer=len).chunk(text)
        self.assertEqual("".join(c.original_text for c in chunks), text)
        for chunk in chunks:
            self.assertTrue(chunk.original_text)
            self.assertLessEqual(len(chunk.embedding_text), 360)
            self.assertEqual(chunk.token_count, len(chunk.embedding_text))
        return chunks

    def test_table_headers_are_repeated_and_rows_remain_complete(self) -> None:
        header = "<tr><th>Name</th><th>Value</th></tr>"
        rows = [f"<tr><td>Item {i}</td><td>{i}</td></tr>" for i in range(12)]
        text = "<table>" + header + "".join(rows) + "</table>"
        chunks = self.chunk(text)
        self.assertGreater(len(chunks), 1)
        rendered_rows = []
        for chunk in chunks:
            root = ElementTree.fromstring(chunk.embedding_text)
            self.assertEqual(root.tag, "table")
            self.assertIn(header, chunk.embedding_text)
            rendered_rows.extend(
                tuple(cell.text for cell in row.findall("td"))
                for row in root.findall("tr") if row.findall("td")
            )
        self.assertEqual(rendered_rows, [(f"Item {i}", str(i)) for i in range(12)])

    def test_html_row_groups_and_merged_cells_preserve_relationships(self) -> None:
        header = "<tr><th>Name</th></tr>"
        row_group = (
            '<tr><td rowspan="2">A</td></tr>'
            '<tr><td colspan="2">B</td></tr>'
        )
        text = (
            "<table><thead>" + header + "</thead><tbody>" + row_group
            + "<tr><td>Other</td></tr>" * 20 + "</tbody></table>"
        )
        chunks = self.chunk(text)
        self.assertTrue(any(row_group in c.original_text for c in chunks))
        for chunk in chunks:
            ElementTree.fromstring(chunk.embedding_text)

    def test_wide_table_cells_are_bounded_and_lossless(self) -> None:
        text = "<table><tr><th>Name</th></tr><tr><td>" + "x" * 1000 + "</td></tr></table>"
        chunks = self.chunk(text)
        self.assertGreater(len(chunks), 1)

    def test_row_labels_are_not_mistaken_for_column_headers(self) -> None:
        first = '<tr><th scope="row">First</th><td>Value</td></tr>'
        text = "<table>" + first + "<tr><td>Other</td></tr>" * 30 + "</table>"
        chunks = self.chunk(text)
        self.assertNotIn(first, chunks[-1].embedding_text)

    def test_markdown_single_column_table_repeats_header(self) -> None:
        header = "| Name |\n| --- |\n"
        text = header + "".join(f"| Item {i} |\n" for i in range(100))
        chunks = self.chunk(text)
        self.assertTrue(all(c.embedding_text.startswith(header) for c in chunks))
        self.assertEqual(
            [line for c in chunks for line in c.embedding_text.splitlines()[2:]],
            [f"| Item {i} |" for i in range(100)],
        )

    def test_markdown_table_headers_after_headings(self) -> None:
        """Repeat column headers rather than preceding heading underlines."""
        rows = [f"| Item {i} | {i} |" for i in range(40)]
        for heading in ("# Inventory\n\n", "Inventory\n---------\n\n", "Inventory\n=========\n", "Inventory | Stock\n-----------------\n\n"):
            for newline in ("\n", "\r\n"):
                with self.subTest(heading=heading, newline=newline):
                    header = "| Name | Value |" + newline + "| --- | --- |" + newline
                    text = heading.replace("\n", newline) + header + newline.join(rows) + newline
                    chunks = self.chunk(text)
                    table_chunks = [chunk for chunk in chunks if "| Item " in chunk.original_text]
                    self.assertGreater(len(table_chunks), 1)
                    for chunk in table_chunks:
                        assert chunk.embedding_text is not None
                        self.assertIn(header, chunk.embedding_text)
                    self.assertEqual([line for chunk in chunks for line in chunk.original_text.splitlines() if line.startswith("| Item ")], rows)

    def test_markdown_table_after_prose_without_blank_line(self) -> None:
        """Recognize a pipe table that immediately follows a paragraph."""
        rows = [f"| Item {i} | {i} |" for i in range(40)]
        for prose in ("Introduction.\n", "First line\nSecond line\n", "Text | not a table\n"):
            for newline in ("\n", "\r\n"):
                with self.subTest(prose=prose, newline=newline):
                    prefix = prose.replace("\n", newline)
                    header = "| Name | Value |" + newline + "| --- | --- |" + newline
                    chunks = self.chunk(prefix + header + newline.join(rows) + newline)
                    self.assertTrue(chunks[0].original_text.startswith(prefix))
                    self.assertGreater(len(chunks), 2)
                    for chunk in chunks:
                        assert chunk.embedding_text is not None
                        self.assertIn(header, chunk.embedding_text)
                    self.assertEqual([line for chunk in chunks for line in chunk.original_text.splitlines() if line.startswith("| Item ")], rows)

    def test_pipe_text_without_a_separator_remains_prose(self) -> None:
        """Do not interpret arbitrary pipe-delimited text as a table."""
        text = "Introduction.\nName | Value\nAlice | 95\n"
        self.assertEqual(self.chunk(text), [Chunk(text, embedding_text=text, token_count=len(text))])

    def test_markdown_table_examples_inside_code_remain_code(self) -> None:
        """Keep table-like lines inside their enclosing fenced code block."""
        header = "| Name | Value |\n| --- | --- |\n"
        text = "```text\nIntroduction.\n" + header + "".join(f"| Item {i} | {i} |\n" for i in range(40)) + "```\n"
        chunks = self.chunk(text)
        for chunk in chunks:
            assert chunk.embedding_text is not None
            self.assertTrue(chunk.embedding_text.startswith("```text\n"))
            self.assertTrue(chunk.embedding_text.rstrip().endswith("```"))
        self.assertEqual(sum(header in chunk.embedding_text for chunk in chunks if chunk.embedding_text is not None), 1)

    def test_fences_and_language_are_repeated(self) -> None:
        text = "```python\n" + "print(1)\n" * 100 + "```\n"
        chunks = self.chunk(text)
        self.assertTrue(all(c.embedding_text.startswith("```python\n") for c in chunks))
        self.assertTrue(all(c.embedding_text.rstrip().endswith("```") for c in chunks))
        self.assertEqual(
            [
                line for c in chunks
                for line in c.embedding_text.splitlines()[1:-1] if line
            ],
            ["print(1)"] * 100,
        )

    def test_complete_sentence_is_not_fragmented_for_a_small_overrun(self) -> None:
        """Keep a fitting sentence whole when a nearby boundary exceeds the goal."""
        first = "Short context sentence. "
        second = "L" * 162 + ". "
        chunks = self.chunk(first + second)
        self.assertEqual(chunks, [Chunk(first + second, embedding_text=first + second, token_count=len(first + second))])

    def test_section_context_does_not_leak_between_siblings(self) -> None:
        text = "# Parent\n\n## First\n\n" + "One sentence. " * 60
        text += "\n\n## Second\n\n" + "Another sentence. " * 60
        chunks = self.chunk(text)
        second = []
        offset = 0
        for chunk in chunks:
            if offset >= text.index("## Second"):
                second.append(chunk)
            offset += len(chunk.original_text)
        self.assertTrue(second)
        self.assertTrue(all("# Parent" in c.embedding_text for c in second))
        self.assertTrue(all("## Second" in c.embedding_text for c in second))
        self.assertTrue(all("## First" not in c.embedding_text for c in second))
        self.assertTrue(all("One sentence." not in c.embedding_text for c in second))

    def test_identical_heading_names_do_not_repeat_previous_section_prose(self) -> None:
        """Preserve repeated headings without adding prose from the preceding section."""
        text = "# Same\n\n" + "First sentence. " * 7 + "\n\n# Same\n\n" + "Second sentence. " * 7
        chunks = self.chunk(text)
        self.assertEqual(len(chunks), 2)
        self.assertNotIn("First sentence.", chunks[1].embedding_text)

    def test_huge_unbroken_block_has_bounded_lossless_fragments(self) -> None:
        text = "x" * 100_000
        chunks = self.chunk(text)
        self.assertGreater(len(chunks), 1)
        self.assertTrue(all(c.embedding_text == c.original_text for c in chunks))

    def test_page_markers_inside_tables_are_assigned_and_code_markers_ignored(self) -> None:
        text = '<!-- InputPageNumber: 1 -->\n\n'
        text += "<table><tr><td>A</td></tr>\n<!-- InputPageNumber: 2 -->\n"
        text += "<tr><td>B</td></tr></table>\n\n"
        text += '```\n<!-- InputPageNumber: 99 -->\n```\n'
        chunks = self.chunk(text)
        self.assertEqual({p for c in chunks for p in c.page_numbers}, {1, 2})
        code_chunks = [c for c in chunks if "```" in c.embedding_text]
        self.assertTrue(code_chunks)
        self.assertTrue(all(2 in c.page_numbers and 99 not in c.page_numbers for c in code_chunks))

    def test_given_nested_fenced_examples_when_chunking_then_ignores_their_page_markers(self) -> None:
        """Keep code examples out of citations for fitting and split documents."""
        examples = (
            "- Example:\n    ```markdown\n    <!-- InputPageNumber: 99 -->\n    ```\n",
            "1. ```markdown\n   <!-- InputPageNumber: 99 -->\n   ```\n",
            "> ```markdown\n> <!-- InputPageNumber: 99 -->\n> ```\n",
            "> - ~~~~markdown\n>   <!-- InputPageNumber: 99 -->\n>   ~~~\n>   <!-- InputPageNumber: 98 -->\n>   ~~~~\n",
        )
        for example in examples:
            text = "<!-- InputPageNumber: 1 -->\n\n" + example + "\nReal page one. " * 20
            text += "\n\n<!-- InputPageNumber: 2 -->\n\nReal page two. " * 10
            for size in (100, len(text)):
                with self.subTest(example=example, chunk_size=size):
                    chunks = MarkdownTokenChunker(chunk_size=size, tokenizer=len).chunk(text)

                    self.assertEqual("".join(chunk.original_text for chunk in chunks), text)
                    self.assertEqual({page for chunk in chunks for page in chunk.page_numbers}, {1, 2})

    def test_given_nested_unclosed_fence_when_chunking_then_ignores_example_markers_to_eof(self) -> None:
        """Do not treat unclosed nested code as a real page transition."""
        text = "<!-- InputPageNumber: 3 -->\n\n- Example:\n    ```markdown\n    <!-- InputPageNumber: 99 -->\n"

        chunks = MarkdownTokenChunker(chunk_size=40, tokenizer=len).chunk(text)

        self.assertEqual("".join(chunk.original_text for chunk in chunks), text)
        self.assertEqual({page for chunk in chunks for page in chunk.page_numbers}, {3})

    def test_given_container_like_code_when_chunking_then_does_not_close_the_outer_fence(self) -> None:
        """Do not reinterpret list or quote prefixes inside an already open fence."""
        for prefix in ("", "> "):
            for code_line in ("- ```", "> ```"):
                text = "<!-- InputPageNumber: 1 -->\n\n" + prefix + "```markdown\n"
                text += prefix + code_line + "\n" + prefix + "<!-- InputPageNumber: 99 -->\n"
                text += prefix + "```\n\n<!-- InputPageNumber: 2 -->\n\nReal page two."
                with self.subTest(prefix=prefix, code_line=code_line):
                    chunks = MarkdownTokenChunker(chunk_size=80, tokenizer=len).chunk(text)

                    self.assertEqual("".join(chunk.original_text for chunk in chunks), text)
                    self.assertEqual({page for chunk in chunks for page in chunk.page_numbers}, {1, 2})

    def test_oversized_context_is_logged_and_preserved_in_source(self) -> None:
        text = "# " + "Title" * 200 + "\n\n" + "Body. " * 100
        with self.assertLogs("ingestra.chunker._token", level="WARNING"):
            chunks = self.chunk(text)
        self.assertIn("# " + "Title" * 200, "".join(c.original_text for c in chunks))

    def test_oversized_table_header_is_not_silently_lost(self) -> None:
        header = "<tr><th>" + "Column " * 100 + "</th></tr>"
        text = "<table>" + header + "<tr><td>Value</td></tr>" * 10 + "</table>"
        with self.assertLogs("ingestra.chunker._token", level="WARNING"):
            chunks = self.chunk(text)
        self.assertIn(header, "".join(c.original_text for c in chunks))
        self.assertGreater(len(chunks), 1)

    def test_bom_crlf_unicode_metadata_and_special_tokens(self) -> None:
        for text in (
            "\ufeff---\r\ntitle: test\r\n---\r\n\r\n" + "\u4e2d\u6587\U0001f600 " * 100,
            "<figure>\n<figcaption>" + "caption " * 100 + "</figcaption></figure>",
            "---\nvalue: " + "metadata " * 100 + "\n---\nBody",
            "<!-- comment " + "x" * 1000,
            "~~~\n" + "a" * 1000,
        ):
            with self.subTest(prefix=text[:15]):
                self.chunk(text)

    def test_real_tokenizer_accepts_special_token_literals_and_multilingual_text(self) -> None:
        import tiktoken
        text = "<|endoftext|>\u4e2d\u6587\U0001f600 " * 1000
        chunks = MarkdownTokenChunker(chunk_size=64).chunk(text)
        encoding = tiktoken.get_encoding("cl100k_base")
        self.assertEqual("".join(c.original_text for c in chunks), text)
        for chunk in chunks:
            self.assertLessEqual(len(encoding.encode_ordinary(chunk.embedding_text)), 80)
        self.assertNotIn("\ufffd", "".join(c.original_text for c in chunks))

    def test_invalid_token_settings(self) -> None:
        for options in (
            {"chunk_size": 0}, {"chunk_size": -1}, {"chunk_size": True},
            {"chunk_size": 10.5}, {"chunk_size": None},
            {"chunk_size": 100, "tokenizer": "not callable"},
        ):
            with self.subTest(options=options), self.assertRaises((TypeError, ValueError)):
                MarkdownTokenChunker(**options)

    def test_tokenizer_errors_and_invalid_counts_are_not_hidden(self) -> None:
        """Reject invalid counts and token IDs, and propagate tokenizer failures."""
        for value in (-1, True, 1.5, None, [1, 2, 3]):
            with self.subTest(value=value), self.assertRaisesRegex(
                ValueError, "nonnegative integer"
            ):
                MarkdownTokenChunker(chunk_size=10, tokenizer=lambda text: value).chunk("text")
        def fail(text: str) -> int:
            raise RuntimeError("provider failure")
        with self.assertRaisesRegex(RuntimeError, "provider failure"):
            MarkdownTokenChunker(chunk_size=10, tokenizer=fail).chunk("text")

    def test_impossible_unicode_character_budget_raises_instead_of_looping(self) -> None:
        with self.assertRaisesRegex(ValueError, "Cannot fit source character"):
            MarkdownTokenChunker(chunk_size=1, tokenizer=lambda text: len(text.encode("utf-8"))).chunk("\U0001f600")

    def test_empty_and_whitespace_only_token_mode(self) -> None:
        chunker = MarkdownTokenChunker(chunk_size=10, tokenizer=len)
        for text in ("", " ", "\r\n\t"):
            self.assertEqual(chunker.chunk(text), [])

    def test_given_missing_tiktoken_when_using_default_tokenizer_then_reports_recovery(self) -> None:
        """Explain how to restore the required tokenizer or override it."""
        with patch.dict("sys.modules", {"tiktoken": None}):
            with self.assertRaisesRegex(ImportError, "requires tiktoken; reinstall ingestra or supply a tokenizer"):
                MarkdownTokenChunker(chunk_size=10)

    def test_invalid_size_is_rejected_before_loading_the_default_tokenizer(self) -> None:
        """Keep configuration errors independent of tokenizer installation."""
        with patch.dict("sys.modules", {"tiktoken": None}):
            with self.assertRaisesRegex(ValueError, "chunk_size must be positive"):
                MarkdownTokenChunker(chunk_size=0)
            with self.assertRaisesRegex(TypeError, "chunk_size must be an integer"):
                MarkdownTokenChunker(chunk_size=True)

    def test_default_tokenizer_counts_ordinary_ids_and_loads_encoding_once(self) -> None:
        """Resolve cl100k_base in the public class and return integer counts."""
        encoding = Mock()
        encoding.encode_ordinary.side_effect = lambda text: list(range(len(text)))
        tiktoken_module = Mock()
        tiktoken_module.get_encoding.return_value = encoding
        with patch.dict("sys.modules", {"tiktoken": tiktoken_module}):
            chunker = MarkdownTokenChunker(chunk_size=10)
            first = chunker.chunk("Body.")
            second = chunker.chunk("Next.")

        tiktoken_module.get_encoding.assert_called_once_with("cl100k_base")
        self.assertEqual(first, [Chunk("Body.", embedding_text="Body.", token_count=5)])
        self.assertEqual(second, [Chunk("Next.", embedding_text="Next.", token_count=5)])
        self.assertIn(("Body.",), [call.args for call in encoding.encode_ordinary.call_args_list])
        self.assertIn(("Next.",), [call.args for call in encoding.encode_ordinary.call_args_list])

    def test_custom_tokenizer_is_passed_to_the_engine_without_default_resolution(self) -> None:
        """Resolve no default tokenizer when the caller supplies its own."""
        with patch.object(MarkdownTokenChunker, "_default_tokenizer") as default, patch("ingestra.chunker.markdown._TokenChunker") as engine:
            MarkdownTokenChunker(chunk_size=100, tokenizer=len)

        default.assert_not_called()
        engine.assert_called_once_with(100, len)

    def test_tokenizer_results_are_not_cached(self) -> None:
        """Recount the same input on a subsequent operation instead of reusing a prior result."""
        tokenizer = Mock(side_effect=[5, 6])
        chunker = MarkdownTokenChunker(chunk_size=100, tokenizer=tokenizer)

        self.assertEqual(chunker.chunk("Body."), [Chunk("Body.", embedding_text="Body.", token_count=5)])
        self.assertEqual(chunker.chunk("Body."), [Chunk("Body.", embedding_text="Body.", token_count=6)])
        self.assertEqual([call.args for call in tokenizer.call_args_list], [("Body.",), ("Body.",)])

    def test_legacy_nested_html_table_does_not_end_at_inner_close(self) -> None:
        table = "<table><tr><td><table><tr><td>A</td></tr></table>\n\n"
        table += "# Still a cell\n</td></tr></table>\n\n"
        text = table + "# Next\n" + "Body. " * 30
        chunks = MarkdownTokenChunker(chunk_size=len(table) + 20, tokenizer=len).chunk(text)
        self.assertTrue(chunks[0].original_text.startswith(table))
        self.assertEqual("".join(chunk.original_text for chunk in chunks), text)

    def test_deterministic_adversarial_documents_and_small_budgets(self) -> None:
        rng = random.Random(8471)
        atoms = [
            "Text without a blank line\n", "English sentence. \u4e2d\u6587\u53e5\u5b50\u3002 ",
            "\U0001f600" * 20, "# Section\n\n", "\r\n  \r\n",
            '<table data-label="a>b"><tr><td>' + "cell " * 20 + "</td></tr></table>\n",
            "```json\n" + '{"a": 1}\n' * 20 + "```\n",
            "<figure>\n" + "caption\n" * 20 + "</figure>\n",
            "<!-- InputPageNumber: 7 -->\n\n", "<!-- incomplete\n\n",
            "| Name | Value |\n| --- | --- |\n| A | 10 |\n\n",
        ]
        with patch("ingestra.chunker._token.logger.warning"):
            for case in range(30):
                text = "".join(rng.choices(atoms, k=8))
                for maximum in (8, 32, 96):
                    with self.subTest(case=case, maximum=maximum):
                        chunks = MarkdownTokenChunker(chunk_size=maximum, tokenizer=len).chunk(text)
                        self.assertEqual("".join(c.original_text for c in chunks), text)
                        for chunk in chunks:
                            self.assertLessEqual(len(chunk.embedding_text), maximum * 2)
                            self.assertTrue(chunk.original_text)


if __name__ == "__main__":
    unittest.main()
