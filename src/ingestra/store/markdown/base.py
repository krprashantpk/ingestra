"""Provider-independent asynchronous storage for embedded Markdown chunks."""

from abc import ABC, abstractmethod
from collections.abc import Callable, Sequence
from copy import deepcopy

from ...types import EmbeddedChunk


class BaseMarkdownStore(ABC):
    """Map embedded chunks before passing complete documents to a provider."""

    async def store_markdown(self, chunks: Sequence[EmbeddedChunk], *, chunk_mapper: Callable[[EmbeddedChunk], dict[str, object]]) -> None:
        """Map and store chunks in source order without document-level metadata.

        All mappings are deep-copied before any writes. Empty sequences do not
        perform writes. Mappers own keys, source positions, linking fields, text,
        and embeddings; providers never generate embeddings or add fields.

        Args:
            chunks: Embedded Markdown chunks in source order.
            chunk_mapper: Synchronous callback returning a complete storage document for each chunk.

        Raises:
            TypeError: Chunks, the mapper, or a mapped document have an unsupported type.
        """
        if not isinstance(chunks, Sequence) or isinstance(chunks, (str, bytes, bytearray)):
            raise TypeError("chunks must be a sequence of EmbeddedChunk objects")
        if not callable(chunk_mapper):
            raise TypeError("chunk_mapper must be callable")

        documents: list[dict[str, object]] = []
        for chunk in chunks:
            if not isinstance(chunk, EmbeddedChunk):
                raise TypeError("chunks must contain only EmbeddedChunk objects")
            document = chunk_mapper(chunk)
            if not isinstance(document, dict):
                raise TypeError("chunk_mapper must return a dictionary")
            documents.append(deepcopy(document))

        if documents:
            await self._store_documents(documents)

    @abstractmethod
    async def _store_documents(self, documents: list[dict[str, object]]) -> None:
        """Persist already mapped documents using the provider's write semantics.

        Args:
            documents: Nonempty list of independent storage documents.
        """
        raise NotImplementedError
