"""Shared models for document ingestion."""

from dataclasses import dataclass

__all__ = ["ChunkResult", "EmbeddedChunk"]


@dataclass(frozen=True)
class EmbeddedChunk:
    """Describe embedded source text with its original page attribution.

    Attributes:
        original_text: Exact source text supplied by the chunker.
        embedding_text: Complete input sent to the embedding provider.
        embedding: Vector generated for the embedding input.
        page_numbers: Source page numbers, or an empty tuple when unavailable.
    """

    original_text: str
    embedding_text: str
    embedding: list[float]
    page_numbers: tuple[int, ...] = ()


@dataclass(frozen=True)
class ChunkResult:
    """Embedded chunks in source order and document-level conversion metadata."""

    chunks: list[EmbeddedChunk]
    metadata: dict[str, object]
