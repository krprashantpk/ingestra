"""Provider-independent asynchronous storage for document-level metadata."""

from abc import ABC, abstractmethod
from collections.abc import Callable
from copy import deepcopy


class BaseMetadataStore(ABC):
    """Map document metadata independently of Markdown chunk storage."""

    async def store_metadata(self, metadata: dict[str, object], *, metadata_mapper: Callable[[dict[str, object]], dict[str, object]]) -> None:
        """Map and store one document, including when its source metadata is empty.

        Args:
            metadata: Document-level metadata without embedded chunks.
            metadata_mapper: Synchronous callback returning a complete storage document with its key.

        Raises:
            TypeError: Metadata, the mapper, or the mapped document have an unsupported type.
        """
        if not isinstance(metadata, dict):
            raise TypeError("metadata must be a dictionary")
        if not callable(metadata_mapper):
            raise TypeError("metadata_mapper must be callable")
        document = metadata_mapper(metadata)
        if not isinstance(document, dict):
            raise TypeError("metadata_mapper must return a dictionary")
        await self._store_documents([deepcopy(document)])

    @abstractmethod
    async def _store_documents(self, documents: list[dict[str, object]]) -> None:
        """Persist already mapped documents using the provider's write semantics.

        Args:
            documents: Nonempty list of independent storage documents.
        """
        raise NotImplementedError
