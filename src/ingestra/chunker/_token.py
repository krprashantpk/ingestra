"""Pack Markdown near one token-size goal using progressively finer boundaries.

The structure parser supplies sections, blocks, sentences, code lines, and
table rows. The token engine fills across those boundaries, refines individually
oversized units, and renders only the structural context needed at each cut.
"""

import logging
import re
from bisect import bisect_left, bisect_right
from collections.abc import Callable, Sequence

from ._structure import _Layout, _Unit, _iter_fenced_code_ranges, _parse_units, _split_layout
from .base import Chunk

logger = logging.getLogger(__name__)
_PAGE = re.compile(r"<!--\s*InputPageNumber\s*[:=]\s*[\"']?(\d+)[\"']?\s*-->")
_ROW_END = re.compile(r"</tr\s*>", re.IGNORECASE)
_CELL_END = re.compile(r"</t[dh]\s*>", re.IGNORECASE)
_LINE_END = re.compile(r"\r\n|\r|\n")
_WORD_END = re.compile(r"[ \t]+")


class _TokenChunker:
    """Coordinate recursive boundary selection and exact embedding-token counts."""

    def __init__(self, chunk_size: int, tokenizer: Callable[[str], int]) -> None:
        """Store the validated size goal and caller-resolved token counter.

        Args:
            chunk_size: Desired complete embedding-input size in tokens.
            tokenizer: Callable returning an exact nonnegative integer token count.
        """
        self.chunk_size = chunk_size
        self.tokenizer = tokenizer

    def chunk(self, text: str) -> list[Chunk]:
        """Pack source ranges near the goal without duplicating source or prose.

        Args:
            text: Source Markdown validated by the public entry point.

        Returns:
            Ordered source slices, structural embedding context, token counts, and pages.

        Raises:
            ValueError: A token count is invalid or one source character cannot fit.
        """
        if not text.strip():
            return []

        def count(value: str) -> int:
            """Validate a result from the configured token counter."""
            result = self.tokenizer(value)
            if isinstance(result, bool) or not isinstance(result, int) or result < 0:
                raise ValueError("tokenizer must return a nonnegative integer")
            return result

        units = _parse_units(text)
        pages = self._find_page_markers(text)
        source_tokens = count(text)
        if source_tokens <= self.chunk_size:
            return [Chunk(text, text, source_tokens, tuple(sorted({page for _, page in pages})))]
        layouts = [_split_layout(text, unit) for unit in units]
        ends = [unit.end for unit in units]
        page_offsets = [offset for offset, _ in pages]
        chunks: list[Chunk] = []
        warned: set[int] = set()
        start = 0
        while start < len(text):
            def render(end: int) -> tuple[str, set[int]]:
                """Render a candidate source range with its structural context."""
                return self._render(text, units, layouts, ends, start, end, count)

            def measure(end: int) -> int:
                """Count the complete embedding input at a candidate boundary."""
                return count(render(end)[0])

            end = self._choose_end(text, units, layouts, ends, start, measure, count)
            embedding_text, omitted = render(end)
            for index in sorted(omitted - warned):
                logger.warning("Embedding context omitted for block at offset %d to keep content near chunk_size=%d", units[index].start, self.chunk_size)
            warned.update(omitted)
            active_page = bisect_right(page_offsets, start) - 1
            chunk_pages = {page for position, page in pages if start <= position < end}
            if active_page >= 0:
                chunk_pages.add(pages[active_page][1])
            chunks.append(Chunk(text[start:end], embedding_text, count(embedding_text), tuple(sorted(chunk_pages))))
            start = end
        return chunks

    def _choose_end(
        self,
        text: str,
        units: Sequence[_Unit],
        layouts: Sequence[_Layout],
        ends: Sequence[int],
        start: int,
        measure: Callable[[int], int],
        count: Callable[[str], int],
    ) -> int:
        """Refine the block around the token goal until a natural cut is usable.

        Args:
            text: Complete source Markdown.
            units: Parsed source blocks in source order.
            layouts: Sentence, line, and row boundaries for those blocks.
            ends: Exclusive source end of each block.
            start: Beginning of the next source slice.
            measure: Complete embedding-token count for a candidate end.
            count: Validated raw token-count callable.

        Returns:
            A progressing source end near the goal, possibly above it at a natural boundary.

        Raises:
            ValueError: One source character alone exceeds the requested size.
        """
        position = max(start, self._fitting_boundary(range(start + 1, len(text) + 1), lambda end, limit: measure(end) <= limit, self.chunk_size))
        if position == len(text):
            return position
        index = bisect_left(ends, max(start + 1, position))
        unit = units[index]
        patterns = (_ROW_END, _CELL_END, _LINE_END, _WORD_END) if unit.kind == "table" else (_LINE_END, _WORD_END)

        def distance(end: int) -> tuple[int, bool]:
            """Prefer the nearest token count and an under-goal cut when tied."""
            tokens = measure(end)
            return abs(tokens - self.chunk_size), tokens > self.chunk_size

        def refine(boundaries: Sequence[int], begin: int, finish: int, level: int) -> int:
            """Descend oversized semantic units through finer separators."""
            location = bisect_right(boundaries, position)
            before = boundaries[location - 1] if location else begin
            after = boundaries[location] if location < len(boundaries) else finish
            if before == position and before > start:
                return before
            left = max(start, before)

            def raw_fits(end: int, limit: int) -> bool:
                """Check a raw semantic prefix without counting a huge remaining suffix."""
                return count(text[left:end]) <= limit

            if self._fitting_boundary(range(left + 1, after + 1), raw_fits, self.chunk_size) == after:
                candidates = [before, after] if before > start else [after]
                return min(candidates, key=distance)
            if level == len(patterns):
                if position > start:
                    return position
                if count(text[start:start + 1]) > self.chunk_size:
                    raise ValueError(f"Cannot fit source character at offset {start} within chunk_size={self.chunk_size}; increase chunk_size")
                return start + 1
            finer = [match.end() for match in patterns[level].finditer(text, left, after)]
            if not finer or finer[-1] != after:
                finer.append(after)
            return refine(finer, left, after, level + 1)

        return refine(layouts[index].boundaries, unit.start, unit.end, 0)

    def _render(
        self,
        text: str,
        units: Sequence[_Unit],
        layouts: Sequence[_Layout],
        ends: Sequence[int],
        start: int,
        end: int,
        count: Callable[[str], int],
    ) -> tuple[str, set[int]]:
        """Add only the headings and wrappers needed at the two source cuts.

        Args:
            text: Complete unchanged source Markdown.
            units: Source blocks and their active headings.
            layouts: Repeatable code fences and explicit table headers.
            ends: Exclusive source ends for locating the cut blocks.
            start: Inclusive source start of this candidate.
            end: Exclusive source end of this candidate.
            count: Validated token-count callable.

        Returns:
            Embedding input and indices whose optional context was omitted.
        """
        first = bisect_right(ends, start)
        last = bisect_left(ends, end)
        omitted: set[int] = set()
        pieces: list[str] = []
        for index in range(first, last + 1):
            unit = units[index]
            layout = layouts[index]
            left, right = max(start, unit.start), min(end, unit.end)
            body = text[left:right]
            partial = left > unit.start or right < unit.end
            if unit.kind == "table" and layout.opening and partial:
                body = re.sub(r"</?(?:thead|tbody|tfoot)\b[^>]*>", "", body, flags=re.IGNORECASE)
            prefix = layout.opening if index == first and left >= layout.opening_end else ""
            suffix = layout.closing if index == last and layout.opening_end < right <= layout.closing_start else ""
            if count(layout.opening + layout.closing) > self.chunk_size // 2:
                if prefix or suffix:
                    omitted.add(index)
                prefix = suffix = ""
            if index == first and layout.header and left >= layout.header_end:
                if count(layout.opening + layout.header + layout.closing) <= self.chunk_size // 2:
                    prefix += layout.header
                else:
                    omitted.add(index)
            pieces.append(prefix + body + suffix)
        body = "".join(pieces)
        context, dropped = self._heading_context(units[first].headings, body, count) if start else ([], False)
        if dropped:
            omitted.add(first)
        return ("\n\n".join(context) + "\n\n" if context else "") + body, omitted

    def _heading_context(self, headings: tuple[str, ...], body: str, count: Callable[[str], int]) -> tuple[list[str], bool]:
        """Select heading context without letting oversized headings dominate a chunk.

        Args:
            headings: Active headings at the start of the source range.
            body: Candidate embedding body including structural wrappers.
            count: Validated token-count callable.

        Returns:
            Bounded context headings and whether any optional heading was omitted.
        """
        context: list[str] = []
        omitted = False
        lines = set(body.splitlines()) if headings else set()
        for heading in reversed(headings):
            if heading in lines:
                continue
            if count(heading) <= self.chunk_size // 4 and count("\n".join([heading] + context)) <= self.chunk_size // 4:
                context.insert(0, heading)
            else:
                omitted = True
        return context, omitted

    @staticmethod
    def _find_page_markers(text: str) -> list[tuple[int, int]]:
        """Locate page markers outside fenced examples.

        Args:
            text: Source Markdown containing optional page comments.

        Returns:
            Ordered source offsets and page numbers.
        """
        ranges = list(_iter_fenced_code_ranges(text))
        range_ends = [end for _, end in ranges]
        pages: list[tuple[int, int]] = []
        for match in _PAGE.finditer(text):
            index = bisect_right(range_ends, match.start())
            if index == len(ranges) or match.start() < ranges[index][0]:
                pages.append((match.start(), int(match[1])))
        return pages

    @staticmethod
    def _fitting_boundary(candidates: Sequence[int], fits: Callable[[int, int], bool], limit: int) -> int:
        """Find a fitting prefix with exponential probing and binary refinement.

        Args:
            candidates: Increasing candidate source ends.
            fits: Predicate measuring a candidate against a token budget.
            limit: Token-count budget used to locate the approximate goal.

        Returns:
            A fitting source end, or zero if no candidate fits.
        """
        if not candidates:
            return 0
        low, high, best = 0, 1, 0
        while high <= len(candidates):
            candidate = candidates[high - 1]
            if not fits(candidate, limit):
                break
            best = candidate
            low = high
            high *= 2
        high = min(high, len(candidates))
        while low < high:
            middle = (low + high) // 2
            candidate = candidates[middle]
            if fits(candidate, limit):
                best = candidate
                low = middle + 1
            else:
                high = middle
        return best
