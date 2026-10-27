"""Compose conversion, chunking, embeddings, and optional persistence."""

import logging
from collections.abc import Callable, Sequence

from .chunker.base import BaseChunker
from .converter.base import BaseConverter
from .embeddings.base import BaseEmbeddings
from .store.markdown.base import BaseMarkdownStore
from .store.metadata.base import BaseMetadataStore
from .types import ChunkResult, EmbeddedChunk

__all__ = ["ChunkResult", "EmbeddedChunk", "Pipeline"]

logger = logging.getLogger(__name__)


class Pipeline:
    """Run caller-configured ingestion components without owning their clients."""

    def __init__(self, converter: BaseConverter, chunker: BaseChunker, embeddings: BaseEmbeddings, *, markdown_store: BaseMarkdownStore | None = None, metadata_store: BaseMetadataStore | None = None) -> None:
        """Configure processing components and independently optional stores.

        Args:
            converter: Caller-configured document converter.
            chunker: Caller-configured Markdown chunker.
            embeddings: Caller-configured embedding generator.
            markdown_store: Optional target for embedded chunks used by ingestion methods.
            metadata_store: Optional target for document metadata used by ingestion methods.
        """
        self._converter = converter
        self._chunker = chunker
        self._embeddings = embeddings
        self._markdown_store = markdown_store
        self._metadata_store = metadata_store

    async def convert(self, data: bytes) -> tuple[str, dict[str, object]]:
        """Convert document bytes to Markdown and document-level metadata.

        Args:
            data: Raw document bytes accepted by the configured converter.

        Returns:
            Markdown text and document metadata, in that order.

        Raises:
            TypeError: Data is not bytes.
        """
        if not isinstance(data, bytes):
            raise TypeError("data must be bytes")

        return await self._converter.convert(data)

    async def chunk(self, markdown: str) -> list[EmbeddedChunk]:
        """Chunk Markdown and embed each chunk in order without conversion.

        Use the chunker's embedding text when present, otherwise its original
        text. Preserve each chunk's source page numbers in the embedded result.
        Empty chunk lists skip embedding generation.
        Invalid inputs and component errors propagate; mismatched embedding
        counts raise RuntimeError. Provider limits and client cleanup remain
        the caller's responsibility.

        Args:
            markdown: Markdown text to chunk and embed.

        Returns:
            Embedded chunks in source order, or an empty list when no chunks exist.

        Raises:
            TypeError: Markdown is not a string.
            RuntimeError: The embedding provider returns the wrong number of vectors.
        """
        if not isinstance(markdown, str):
            raise TypeError("markdown must be a string")

        chunks = self._chunker.chunk(markdown)
        if not chunks:
            return []

        texts = [
            chunk.embedding_text
            if chunk.embedding_text is not None
            else chunk.original_text
            for chunk in chunks
        ]
        vectors = await self._embeddings.generate(texts)
        if len(vectors) != len(chunks):
            raise RuntimeError(
                f"embedding provider returned {len(vectors)} embeddings; "
                f"expected {len(chunks)} embeddings (one per chunk)"
            )

        return [
            EmbeddedChunk(original_text=chunk.original_text, embedding_text=text, embedding=vector, page_numbers=chunk.page_numbers)
            for chunk, text, vector in zip(chunks, texts, vectors, strict=True)
        ]

    async def ingest_chunks(self, chunks: Sequence[EmbeddedChunk], *, chunk_mapper: Callable[[EmbeddedChunk], dict[str, object]]) -> None:
        """Persist embedded chunks without conversion or metadata storage.

        Empty sequences perform no provider writes. Store and mapper errors
        propagate unchanged. Clients and transactions remain caller-owned.

        Args:
            chunks: Already embedded Markdown chunks in source order.
            chunk_mapper: Synchronous callback returning a complete storage document for each chunk.

        Raises:
            ValueError: No Markdown store is configured.
            TypeError: The mapper is not callable or the store rejects the input or mapped documents.
        """
        if self._markdown_store is None:
            raise ValueError("ingest_chunks requires a configured markdown_store")
        if not callable(chunk_mapper):
            raise TypeError("chunk_mapper must be callable when markdown_store is configured")

        logger.info("Storing embedded chunks")
        await self._markdown_store.store_markdown(chunks, chunk_mapper=chunk_mapper)
        logger.info("Completed storage of embedded chunks")

    async def ingest_metadata(self, metadata: dict[str, object], *, metadata_mapper: Callable[[dict[str, object]], dict[str, object]]) -> None:
        """Persist document metadata without conversion or chunk storage.

        Empty metadata still produces a mapped document. Store and mapper errors
        propagate unchanged. Clients and transactions remain caller-owned.

        Args:
            metadata: Document-level metadata to persist.
            metadata_mapper: Synchronous callback returning a complete storage document with its key.

        Raises:
            ValueError: No metadata store is configured.
            TypeError: The mapper is not callable or the store rejects the input or mapped document.
        """
        if self._metadata_store is None:
            raise ValueError("ingest_metadata requires a configured metadata_store")
        if not callable(metadata_mapper):
            raise TypeError("metadata_mapper must be callable when metadata_store is configured")

        logger.info("Storing document metadata")
        await self._metadata_store.store_metadata(metadata, metadata_mapper=metadata_mapper)
        logger.info("Completed storage of document metadata")

    