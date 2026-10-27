"""Recognize Markdown structure without applying any token budget.

Start with _parse_units to attach section headings to source blocks.
Use _split_layout to find sentence, code-line, or table-row boundaries.
The remaining helpers implement Markdown and HTML recognition.
"""

import re
from collections.abc import Iterator, Sequence
from dataclasses import dataclass
from html.parser import HTMLParser

_ATX_HEADING = re.compile(r" {0,3}#{1,6}(?:[ \t]+|$)")
_SETEXT_UNDERLINE = re.compile(r" {0,3}(?:=+|-+)[ \t]*$")
_FENCE = re.compile(r" {0,3}(`{3,}|~{3,})")
_CONTAINER_PREFIX = re.compile(r"^[ \t]*(?:(?:>[ \t]?|(?:[-+*]|\d{1,9}[.)])[ \t]+)[ \t]*)*")
_HTML_START = re.compile(r" {0,3}(?:<(table|figure)\b|<!--)", re.IGNORECASE)
_SENTENCE = re.compile(r"[.!?。！？](?:\s+|(?=[^\x00-\x7f])|$)")
_TABLE_RULE = re.compile(r"^\s*\|?\s*:?-{3,}:?\s*(?:\|\s*:?-{3,}:?\s*)*\|?\s*$")


@dataclass(frozen=True)
class _Unit:
    """Describe a source block together with its active section headings.

    Attributes:
        start: Inclusive character offset in the original document.
        end: Exclusive character offset in the original document.
        kind: Recognized block type, such as text, code, table, or comment.
        headings: Active headings from the outermost section to the innermost.
        section_start: Whether this unit includes newly encountered headings.
    """

    start: int
    end: int
    kind: str
    headings: tuple[str, ...]
    section_start: bool = False


@dataclass(frozen=True)
class _Layout:
    """Describe preferred split points and repeatable structural context.

    Attributes:
        boundaries: Source offsets after complete sentences, lines, or row groups.
        opening: Opening code fence or HTML table tag to repeat when needed.
        opening_end: Source position after the original opening wrapper.
        closing: Closing code fence or HTML table tag to repeat when needed.
        closing_start: Source position before the original closing wrapper.
        header: Explicit table header to repeat on later fragments.
        header_end: Source position after the original table header.
    """

    boundaries: tuple[int, ...]
    opening: str = ""
    opening_end: int = 0
    closing: str = ""
    closing_start: int = 0
    header: str = ""
    header_end: int = 0


def _iter_fenced_code_ranges(text: str) -> Iterator[tuple[int, int]]:
    """Locate fenced examples, including indented list and blockquote containers.

    Args:
        text: Complete Markdown whose source offsets must remain unchanged.

    Yields:
        Source ranges from each opening fence through its close, or EOF for an unclosed fence.
    """
    closing: re.Pattern[str] | None = None
    start = offset = 0
    for line in text.splitlines(keepends=True):
        source = line.rstrip("\r\n")
        end = offset + len(line)
        if closing is not None:
            if closing.fullmatch(source):
                yield start, end
                closing = None
        else:
            normalized = _CONTAINER_PREFIX.sub("", source)
            fence = _FENCE.match(normalized)
            if fence and (fence[1][0] != "`" or "`" not in normalized[fence.end():]):
                start = offset
                quote_depth = source[:len(source) - len(normalized)].count(">")
                closing = re.compile(rf"[ \t]*(?:>[ \t]*){{{quote_depth}}}{re.escape(fence[1][0])}{{{len(fence[1])},}}[ \t]*")
        offset = end
    if closing is not None:
        yield start, len(text)


def _parse_units(text: str) -> list[_Unit]:
    """Attach active headings to ordered blocks without changing source text.

    Args:
        text: Complete source Markdown.

    Returns:
        Units covering nonblank input, with headings attached to the next block when present.
    """
    result: list[_Unit] = []
    headings: list[tuple[int, str]] = []
    pending: int | None = None
    for block in _iter_blocks(text):
        source = text[block.start:block.end]
        if block.heading:
            lines = source.strip().splitlines()
            atx = _ATX_HEADING.match(lines[0])
            if atx:
                level = len(lines[0].lstrip().split(maxsplit=1)[0])
                title = re.sub(r"[ \t]+#+[ \t]*$", "", lines[0][atx.end():])
            else:
                level = 1 if lines[1].lstrip().startswith("=") else 2
                title = lines[0]
            headings = [(n, h) for n, h in headings if n < level]
            headings.append((level, "#" * level + " " + title.strip()))
            if pending is None:
                pending = block.start
            continue
        result.append(_Unit(block.start if pending is None else pending, block.end, _classify_block(source), tuple(h for _, h in headings), pending is not None))
        pending = None
    if pending is not None:
        result.append(_Unit(pending, len(text), "text", tuple(h for _, h in headings), True))
    return result


def _split_layout(text: str, unit: _Unit) -> _Layout:
    """Find preferred split points and wrappers for one source unit.

    Args:
        text: Complete source Markdown.
        unit: Source block with its active heading context.

    Returns:
        Sentence boundaries for prose, line boundaries for code, or row groups and headers for tables.
    """
    source = text[unit.start:unit.end]
    lines = source.splitlines(keepends=True)
    line_ends: list[int] = []
    end = unit.start
    for line in lines:
        end += len(line)
        line_ends.append(end)
    if unit.kind == "code":
        for index, line in enumerate(lines):
            fence = _FENCE.match(line)
            if fence:
                marker = fence[1]
                closing = re.compile(rf" {{0,3}}{re.escape(marker[0])}{{{len(marker)},}}[ \t]*$")
                close = next((i for i in range(index + 1, len(lines)) if closing.fullmatch(lines[i].rstrip("\r\n"))), len(lines))
                closing_start = line_ends[close - 1] if close else unit.start
                boundaries = [position for position in line_ends[index + 1:close] if position < closing_start]
                return _Layout(tuple(boundaries + [unit.end]), line.rstrip("\r\n") + "\n", line_ends[index], "\n" + marker, closing_start)
    if unit.kind == "table" and re.search(r"<table\b", source, re.I):
        parser = _TableParser(source, unit.start)
        parser.feed(source)
        parser.close()
        if parser.table_count == 1 and parser.rows:
            boundaries: list[int] = []
            required_until = 0
            header_end = 0
            for index, (_, end, header, rowspan) in enumerate(parser.rows):
                required_until = max(required_until, index + rowspan)
                if index + 1 >= required_until:
                    boundaries.append(end)
                if header and (index == 0 or header_end == parser.rows[index - 1][1]):
                    header_end = end
            header = "".join(text[start:end] for start, end, _, _ in parser.rows if end <= header_end)
            return _Layout(
                tuple([position for position in boundaries if position > header_end] + [unit.end]), parser.opening + "\n",
                parser.opening_end, "\n</table>", parser.closing_start,
                header, header_end,
            )
    if unit.kind == "table":
        header_line = next((i for i in range(len(lines) - 1) if _is_table_header(lines, i)), None)
        if header_line is not None:
            rule = header_line + 1
            header_start = line_ends[header_line - 1] if header_line else unit.start
            return _Layout(tuple(line_ends[rule + 1:]) or (unit.end,), header=text[header_start:line_ends[rule]], header_end=line_ends[rule])
    if unit.kind == "text":
        return _Layout(tuple([unit.start + match.end() for match in _SENTENCE.finditer(source)] + [unit.end]))
    return _Layout(tuple(line_ends))


@dataclass(frozen=True)
class _Block:
    """Locate one complete block in the original Markdown.

    Attributes:
        start: Inclusive source offset, including leading whitespace.
        end: Exclusive source offset, including trailing blank lines.
        heading: Whether the block is an ATX or single-line Setext heading.
    """

    start: int
    end: int
    heading: bool


def _iter_blocks(markdown: str) -> Iterator[_Block]:
    """Walk complete blocks while preserving every original source offset.

    Args:
        markdown: Source Markdown with its original whitespace and line endings.

    Yields:
        Block ranges in source order, or no blocks for whitespace-only input.
    """
    lines = markdown.splitlines(keepends=True)
    offsets = [0]
    for line in lines:
        offsets.append(offsets[-1] + len(line))

    index = 0
    while index < len(lines):
        start = index
        while index < len(lines) and not lines[index].strip():
            index += 1
        if index == len(lines):
            return
        end, heading = _find_block_end(lines, index)
        while end < len(lines) and not lines[end].strip():
            end += 1
        yield _Block(offsets[start], offsets[end], heading)
        index = end


def _find_block_end(lines: Sequence[str], start: int) -> tuple[int, bool]:
    """Find where a heading, paragraph, or protected structural block ends.

    Args:
        lines: Source lines with their original line endings.
        start: Index of the first nonblank line in the block.

    Returns:
        The exclusive line index and whether this block is a heading.
    """
    line = lines[start].rstrip("\r\n")
    if start == 0 and line.lstrip("\ufeff") == "---":
        for index in range(start + 1, len(lines)):
            if lines[index].strip() in ("---", "..."):
                return index + 1, False

    fence = _FENCE.match(line)
    if fence:
        marker = fence[1]
        closing = re.compile(rf" {{0,3}}{re.escape(marker[0])}{{{len(marker)},}}[ \t]*$")
        for index in range(start + 1, len(lines)):
            if closing.fullmatch(lines[index].rstrip("\r\n")):
                return index + 1, False
        return len(lines), False

    html = _HTML_START.match(line)
    if html:
        parser = _HTMLBlockEnd(html[1]) if html[1] else None
        for index in range(start, len(lines)):
            if parser is not None:
                parser.feed(lines[index])
            if (parser is not None and parser.closed) or (parser is None and "-->" in lines[index]):
                return index + 1, False
        return len(lines), False

    if _is_heading(lines, start):
        return start + (1 if _ATX_HEADING.match(line) else 2), True

    table = _is_table_header(lines, start)
    end = start + 1
    while end < len(lines) and lines[end].strip():
        next_line = lines[end].rstrip("\r\n")
        if _is_heading(lines, end) or _FENCE.match(next_line) or _HTML_START.match(next_line) or (not table and _is_table_header(lines, end)):
            break
        end += 1
    return end, False


def _is_heading(lines: Sequence[str], index: int) -> bool:
    """Recognize an ATX heading or a single-line Setext heading.

    Args:
        lines: Source lines including any original line endings.
        index: Line to inspect for a heading.

    Returns:
        Whether the current line starts a recognized heading.
    """
    line = lines[index].rstrip("\r\n")
    return bool(_ATX_HEADING.match(line) or (line.strip() and index + 1 < len(lines) and _SETEXT_UNDERLINE.fullmatch(lines[index + 1].rstrip("\r\n"))))


def _is_table_header(lines: Sequence[str], index: int) -> bool:
    """Recognize a pipe-table header and separator without matching headings.

    Args:
        lines: Source lines with or without their original line endings.
        index: Index of the candidate column-header line.

    Returns:
        Whether a non-heading pipe row is immediately followed by a table separator.
    """
    return bool(index + 1 < len(lines) and "|" in lines[index] and _TABLE_RULE.fullmatch(lines[index + 1].strip()) and not _is_heading(lines, index))


def _classify_block(text: str) -> str:
    """Classify a block so later stages can choose suitable split boundaries.

    Args:
        text: Source slice for one non-heading block.

    Returns:
        The recognized block kind, defaulting to ordinary text.
    """
    stripped = text.lstrip("\ufeff \t\r\n")
    if _FENCE.match(stripped):
        return "code"
    if re.match(r"<table\b", stripped, re.I):
        return "table"
    if re.match(r"<figure\b", stripped, re.I):
        return "figure"
    if stripped.startswith("<!--"):
        return "comment"
    if stripped.startswith("---\n") or stripped.startswith("---\r\n"):
        return "metadata"
    lines = stripped.splitlines()
    if _is_table_header(lines, 0):
        return "table"
    return "text"


class _HTMLBlockEnd(HTMLParser):
    """Track nested table or figure tags until the outer block closes."""

    def __init__(self, tag: str) -> None:
        """Initialize nesting state for the selected HTML element.

        Args:
            tag: Table or figure tag whose outer closing tag ends the block.
        """
        super().__init__()
        self.tag = tag.casefold()
        self.depth = 0
        self.closed = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        """Count opening tags for the tracked element.

        Args:
            tag: Opening element name supplied by the HTML parser.
            attrs: Parsed HTML attributes, unused for block nesting.
        """
        if tag == self.tag:
            self.depth += 1

    def handle_endtag(self, tag: str) -> None:
        """Mark the block complete when its outermost tracked tag closes.

        Args:
            tag: Closing element name supplied by the HTML parser.
        """
        if tag == self.tag:
            self.depth -= 1
            if self.depth == 0:
                self.closed = True


class _TableParser(HTMLParser):
    """Locate outer table rows, explicit headers, and merged-cell row groups."""

    def __init__(self, text: str, offset: int) -> None:
        """Initialize table state using absolute source coordinates.

        Args:
            text: Complete source slice containing the HTML table.
            offset: Position of the slice in the original document.
        """
        super().__init__(convert_charrefs=False)
        self.text = text
        self.source_offset = offset
        self.lines = [0] + [match.end() for match in re.finditer("\n", text)]
        self.depth = 0
        self.table_count = 0
        self.opening = ""
        self.opening_end = offset
        self.closing_start = offset + len(text)
        self.row_start = offset
        self.row_header = False
        self.row_has_th = False
        self.row_has_td = False
        self.rowspan = 1
        self.in_head = False
        self.rows: list[tuple[int, int, bool, int]] = []

    def position(self) -> int:
        """Return the parser's absolute character offset in the document.

        Returns:
            Source position of the current HTML event.
        """
        line, column = self.getpos()
        return self.source_offset + self.lines[line - 1] + column

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        """Record outer-table row starts, headers, and rowspan requirements.

        Args:
            tag: Opening element name supplied by the HTML parser.
            attrs: Parsed HTML attributes, including any rowspan value.

        Raises:
            ValueError: An opening table event has no corresponding source tag.
        """
        if tag == "table":
            if self.depth == 0:
                self.table_count += 1
                opening = self.get_starttag_text()
                if opening is None:
                    raise ValueError("HTML parser did not provide the opening table source tag")
                self.opening = opening
                self.opening_end = self.position() + len(self.opening)
            self.depth += 1
        if self.depth != 1:
            return
        if tag == "thead":
            self.in_head = True
        elif tag == "tr":
            self.row_start = self.position()
            self.row_header = self.in_head
            self.row_has_th = self.row_has_td = False
            self.rowspan = 1
        elif tag in ("th", "td"):
            self.row_has_th = self.row_has_th or tag == "th"
            self.row_has_td = self.row_has_td or tag == "td"
            for name, value in attrs:
                if name == "rowspan" and value is not None and value.isdecimal():
                    # rowspan=0 extends to the end of the row group.
                    span = int(value) if len(value) < 7 else len(self.text)
                    self.rowspan = max(self.rowspan, span or len(self.text))

    def handle_endtag(self, tag: str) -> None:
        """Finish outer rows and record the original table's closing position.

        Args:
            tag: Closing element name supplied by the HTML parser.
        """
        if self.depth == 1:
            if tag == "tr":
                relative = self.position() - self.source_offset
                end = self.text.find(">", relative)
                if end != -1:
                    self.rows.append((self.row_start, self.source_offset + end + 1, self.row_header or (self.row_has_th and not self.row_has_td), self.rowspan))
            elif tag == "thead":
                self.in_head = False
            elif tag == "table":
                self.closing_start = self.position()
        if tag == "table":
            self.depth -= 1
