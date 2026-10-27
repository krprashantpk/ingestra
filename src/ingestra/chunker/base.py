"""Shared chunk model and implementation-independent chunking interface."""

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass(frozen=True)
class Chunk:
    """Original text, embedding input, token count, and source page numbers.

    ``original_text`` is the source slice. ``embedding_text`` may add context;
    ``token_count`` describes that embedding input when populated.
    """

    original_text: str
    embedding_text: str | None = None
    token_count: int | None = None
    page_numbers: tuple[int, ...] = ()


class BaseChunker(ABC):
    """Common interface for interchangeable, synchronous text chunkers.

    All implementations return the shared ``Chunk`` model so downstream code
    uses the same fields regardless of the selected chunking strategy.
    """

    @abstractmethod
    def chunk(self, text: str, /) -> list[Chunk]:
        """Always return a list of ``Chunk`` objects in source order.

        Empty or whitespace-only input returns an empty list. Non-string
        input raises ``TypeError``; configuration and processing errors must
        raise explicitly. Chunk boundaries, overlap, and size limits
        remain implementation-specific.

        Input is positional so implementations can keep format-specific
        parameter names.
        """
        raise NotImplementedError
