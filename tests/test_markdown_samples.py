"""Validate the notebook's Markdown scenarios at the default token-size goal."""

import ast
import re
import unittest
from pathlib import Path

import tiktoken

from ingestra.chunker import Chunk, MarkdownTokenChunker

SAMPLES_DIRECTORY = Path(__file__).resolve().parents[1] / "exeperiment" / "chunkers" / "samples"
CHUNK_SIZE = 2048


class MarkdownSampleTests(unittest.TestCase):
    """Keep the demonstration corpus large enough to exercise real structural cuts."""

    encoding: tiktoken.Encoding
    samples: dict[str, str]

    @classmethod
    def setUpClass(cls) -> None:
        """Load the real encoding and preserve each fixture's exact source bytes."""
        cls.encoding = tiktoken.get_encoding("cl100k_base")
        cls.samples = {path.name: path.read_bytes().decode("utf-8") for path in sorted(SAMPLES_DIRECTORY.glob("*.md"))}

    def _ranges(self, text: str) -> list[tuple[int, int, Chunk]]:
        """Return default-sized chunks with their derived original-source ranges."""
        ranges: list[tuple[int, int, Chunk]] = []
        offset = 0
        for chunk in MarkdownTokenChunker().chunk(text):
            end = offset + len(chunk.original_text)
            ranges.append((offset, end, chunk))
            offset = end
        return ranges

    def test_given_samples_when_chunking_then_every_format_exercises_multiple_default_chunks(self) -> None:
        """Measure real source sizes, density, exact counts, and lossless reconstruction."""
        self.assertEqual(len(self.samples), 12)
        for name, text in self.samples.items():
            for size in (2028, CHUNK_SIZE):
                with self.subTest(sample=name, chunk_size=size):
                    self.assertGreaterEqual(len(self.encoding.encode_ordinary(text)), CHUNK_SIZE * 2)

                    chunks = MarkdownTokenChunker(chunk_size=size).chunk(text)

                    self.assertGreaterEqual(len(chunks), 3)
                    self.assertEqual("".join(chunk.original_text for chunk in chunks), text)
                    for chunk in chunks:
                        assert chunk.embedding_text is not None
                        self.assertTrue(chunk.original_text)
                        self.assertEqual(chunk.token_count, len(self.encoding.encode_ordinary(chunk.embedding_text)))
                    for chunk in chunks[:-1]:
                        assert chunk.token_count is not None
                        self.assertLessEqual(abs(chunk.token_count - size), 256)

    def test_given_large_samples_when_the_complete_document_fits_then_returns_one_chunk(self) -> None:
        """Retain fitting-document coverage without making the default-size samples tiny."""
        for name, text in self.samples.items():
            with self.subTest(sample=name):
                size = len(self.encoding.encode_ordinary(text))

                chunks = MarkdownTokenChunker(chunk_size=size).chunk(text)

                self.assertEqual(len(chunks), 1)
                self.assertTrue(chunks[0].original_text == text, "Original source changed")
                self.assertTrue(chunks[0].embedding_text == text, "A fitting document gained context")
                self.assertEqual(chunks[0].token_count, size)
                self.assertEqual(chunks[0].page_numbers, (1, 2, 3, 4) if name == "09_page_markers.md" else ())

    def test_given_stress_sample_when_chunking_then_individually_oversized_units_are_refined(self) -> None:
        """Exercise word, cell, line, and character fallback at 2048 tokens."""
        text = self.samples["12_oversized_and_unclosed_blocks.md"]
        cuts = [end for _, end, _ in self._ranges(text)[:-1]]
        prefixes = (
            "ZXQJ",
            "This single sentence records ",
            "| LONG-1 |",
            "<tr><td>HTML-LONG-1</td>",
            "review_note = ",
        )
        for prefix in prefixes:
            with self.subTest(unit=prefix):
                matches = [line for line in text.splitlines() if line.startswith(prefix)]
                self.assertEqual(len(matches), 1)
                unit = matches[0]
                self.assertGreater(len(self.encoding.encode_ordinary(unit)), CHUNK_SIZE)
                start = text.index(unit)
                self.assertTrue(any(start < cut < start + len(unit) for cut in cuts))
        self.assertFalse(text.rstrip().endswith("```"))

    def test_given_structural_samples_when_measured_then_the_blocks_themselves_exceed_the_goal(self) -> None:
        """Ensure code, tables, metadata, figures, comments, and unclosed blocks really split."""
        scenarios = (
            ("04_fenced_code.md", r"```python\n(.*?)\n```"),
            ("05_markdown_tables.md", r"(\| Document \|.*?)(?=\n## Allowed states)"),
            ("05_markdown_tables.md", r"## Single-column event log\n\n(\| Event \|.*)\Z"),
            ("06_html_tables_and_merged_cells.md", r"(<table>.*?</table>)"),
            ("06_html_tables_and_merged_cells.md", r"## A headerless table.*?(<table>.*?</table>)"),
            ("08_frontmatter_and_setext.md", r"\A---\n(.*?)\n---\n"),
            ("10_figures_and_html_blocks.md", r"## A figure larger.*?(<figure>.*?</figure>)"),
            ("10_figures_and_html_blocks.md", r"## A long hidden.*?(<!--.*?-->)"),
            ("12_oversized_and_unclosed_blocks.md", r"## An unfinished code fence.*?```text\n(.*)\Z"),
        )
        for name, pattern in scenarios:
            with self.subTest(sample=name, scenario=pattern):
                text = self.samples[name]
                match = re.search(pattern, text, re.DOTALL)
                assert match is not None, f"Missing structural scenario in {name}"
                self.assertGreater(len(self.encoding.encode_ordinary(match[1])), CHUNK_SIZE)
                start, end = match.span(1)
                self.assertTrue(any(start < cut < end for _, cut, _ in self._ranges(text)[:-1]))

    def test_given_long_code_and_pipe_tables_when_split_then_context_and_complete_rows_remain(self) -> None:
        """Inspect actual fence continuations and both repeated pipe-table header shapes."""
        text = self.samples["04_fenced_code.md"]
        match = re.search(r"```python\n(.*?)\n```", text, re.DOTALL)
        assert match is not None
        ast.parse(match[1])
        body_start, body_end = match.span(1)
        middle = [chunk for start, end, chunk in self._ranges(text) if body_start <= start < end <= body_end]
        self.assertTrue(middle)
        for chunk in middle:
            assert chunk.embedding_text is not None
            self.assertIn("```python\n", chunk.embedding_text)
            self.assertTrue(chunk.embedding_text.rstrip().endswith("```"))

        text = self.samples["05_markdown_tables.md"]
        chunks = MarkdownTokenChunker().chunk(text)
        first = text.index("| Document |")
        header = "".join(text[first:].splitlines(keepends=True)[:2])
        for row_pattern, expected_header in ((r"^\| DOC-\d+", header), (r"^\| Event \d+", "| Event |\n|-------|\n")):
            rows = [line for line in text.splitlines() if re.match(row_pattern, line)]
            self.assertGreater(len(rows), 20)
            for row in rows:
                with self.subTest(row=row[:32]):
                    owners = [chunk for chunk in chunks if row in chunk.original_text]
                    self.assertEqual(len(owners), 1)
                    assert owners[0].embedding_text is not None
                    self.assertTrue(expected_header in owners[0].embedding_text, "A pipe-table continuation lost its header")

    def test_given_grouped_and_headerless_html_when_split_then_preserves_their_different_semantics(self) -> None:
        """Keep fitting rowspan pairs together and never invent a header for a data-only table."""
        text = self.samples["06_html_tables_and_merged_cells.md"]
        chunks = MarkdownTokenChunker().chunk(text)
        groups = re.findall(r'<tr><td rowspan="2">.*?</tr>\s*<tr>.*?</tr>', text, re.DOTALL)
        self.assertGreater(len(groups), 20)
        for group in groups:
            owners = [chunk for chunk in chunks if group in chunk.original_text]
            self.assertEqual(len(owners), 1)
            assert owners[0].embedding_text is not None
            self.assertIn("<th>Team</th>", owners[0].embedding_text)
        self.assertEqual(sum(chunk.embedding_text.count("<td>Collection</td>") for chunk in chunks if chunk.embedding_text is not None), 1)

    def test_given_paged_and_unicode_samples_when_chunking_then_keeps_real_attribution_and_code_points(self) -> None:
        """Exercise cross-page chunks, fenced marker literals, and non-ASCII source preservation."""
        chunks = MarkdownTokenChunker().chunk(self.samples["09_page_markers.md"])
        self.assertEqual({page for chunk in chunks for page in chunk.page_numbers}, {1, 2, 3, 4})
        self.assertTrue(any(len(chunk.page_numbers) > 1 for chunk in chunks))
        self.assertTrue(all(not chunk.page_numbers for chunk in MarkdownTokenChunker().chunk(self.samples["04_fenced_code.md"])))

        text = self.samples["11_multilingual_and_unicode.md"]
        for literal in ("café", "cafe\u0301", "👩‍👩‍👧‍👦", "👩🏽‍💻", "<|endoftext|>", "<|fim_prefix|>"):
            self.assertIn(literal, text)
        self.assertEqual("".join(chunk.original_text for chunk in MarkdownTokenChunker().chunk(text)), text)
