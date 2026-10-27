"""Public entry point for Markdown token chunking.

Start at MarkdownTokenChunker.chunk. The _token module coordinates token-size
goals, and _structure recognizes blocks and preferred split boundaries.
Neither module makes Azure requests or generates embeddings.
"""

from collections.abc import Callable

from ._token import _TokenChunker
from .base import BaseChunker, Chunk


class MarkdownTokenChunker(BaseChunker):
    """Recursively pack Markdown near a token-based chunk size.

    Use chunk_size as a soft goal, not a character count or hard ceiling.
    Pack across headings and blocks rather than emitting one chunk per section.
    Choose the nearest complete sentence, code line, or table row, allowing
    a boundary or repeated structural context to take a chunk above the goal.
    Only a short document or the final remainder normally stays much smaller.

    Recursively divide an individually oversized sentence, row, or line at
    finer row, cell, line, word, and finally character boundaries. Such
    fallback fragments are not always independently valid Markdown or HTML.
    Content is never silently truncated.

    Add active headings to embedding_text and repeat code fences and explicit
    table headers where possible. Prose overlap is not added. Count all
    structural context in token_count. Disproportionately large optional
    headings or headers may be omitted with a warning to leave room for content.

    Keep original_text as exact, non-overlapping source slices in document
    order. Joining them reconstructs nonblank input. Embed embedding_text, not
    original_text; token_count measures that final input. Track CU page
    comments in page_numbers, ignoring example markers inside fenced code.
    Token and provider errors propagate, and an impossible budget raises.
    """

    def __init__(self, *, chunk_size: int = 2048, tokenizer: Callable[[str], int] | None = None) -> None:
        """Configure the token-size goal and optional caller-supplied tokenizer.

        Args:
            chunk_size: Positive target token count, defaulting to 2048; natural boundaries and structural context may exceed it.
            tokenizer: Callable returning a nonnegative integer token count, not token IDs; defaults to the length of cl100k_base encode_ordinary output from tiktoken.

        Raises:
            TypeError: The size is not an integer, is a boolean, or the tokenizer is not callable.
            ValueError: The size is not positive.
            ImportError: The default tokenizer is requested but tiktoken is missing from the environment.
        """
        if isinstance(chunk_size, bool) or not isinstance(chunk_size, int):
            raise TypeError("chunk_size must be an integer")
        if chunk_size <= 0:
            raise ValueError("chunk_size must be positive")
        if tokenizer is None:
            tokenizer = self._default_tokenizer()
        if not callable(tokenizer):
            raise TypeError("tokenizer must be callable")
        self._token_chunker = _TokenChunker(chunk_size, tokenizer)

    def chunk(self, markdown: str) -> list[Chunk]:
        """Split Markdown into source slices and near-target embedding inputs.

        Args:
            markdown: Source Markdown whose text and order must be preserved.

        Returns:
            Chunks near chunk_size with embedding text, exact token counts, and source pages, or an empty list for blank input.

        Raises:
            TypeError: The source is not a string.
            ValueError: A token count is invalid or even one source character exceeds the size goal.
        """
        if not isinstance(markdown, str):
            raise TypeError("markdown must be a string")
        return self._token_chunker.chunk(markdown)

    @staticmethod
    def pages_to_markdown(pages: list[str]) -> str:
        """Join page strings with one-based InputPageNumber comments.

        Args:
            pages: Page contents in source order, preserved verbatim, including empty pages.

        Returns:
            Markdown with a page marker and blank line before each page, separated by blank lines, or an empty string for an empty list.

        Raises:
            TypeError: The input is not a list or a page is not a string.
        """
        if not isinstance(pages, list):
            raise TypeError("pages must be a list of strings")
        for index, page in enumerate(pages):
            if not isinstance(page, str):
                raise TypeError(f"pages[{index}] must be a string")
        return "\n\n".join(f"<!-- InputPageNumber: {number} -->\n\n{page}" for number, page in enumerate(pages, start=1))

    @staticmethod
    def _default_tokenizer() -> Callable[[str], int]:
        """Create the default cl100k_base token-count callable.

        Returns:
            A tokenizer returning the length of ordinary token IDs, including special-token literals.

        Raises:
            ImportError: The required tiktoken dependency is not installed.
        """
        try:
            import tiktoken
        except ModuleNotFoundError as exc:
            if exc.name != "tiktoken":
                raise
            raise ImportError("The default tokenizer requires tiktoken; reinstall ingestra or supply a tokenizer") from exc
        encoding = tiktoken.get_encoding("cl100k_base")

        def tokenizer(text: str) -> int:
            """Return the number of ordinary cl100k_base tokens.

            Args:
                text: Complete embedding input or candidate fragment.

            Returns:
                The number of token IDs produced by ordinary encoding.
            """
            return len(encoding.encode_ordinary(text))

        return tokenizer
