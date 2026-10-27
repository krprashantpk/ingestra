"""Provider-independent interface for asynchronous binary conversion."""

from abc import ABC, abstractmethod


class BaseConverter(ABC):
    """Common interface for interchangeable binary-to-Markdown converters.

    Supported formats, configuration, and resource ownership remain
    implementation-specific.
    """

    @abstractmethod
    async def convert(self, data: bytes) -> tuple[str, dict[str, object]]:
        """Return Markdown text and metadata, in that order.

        Metadata keys are strings; values may be any Python object. Return
        an empty dictionary when no metadata is available. Non-bytes input
        must raise ``TypeError``; unsupported formats and conversion errors
        must raise explicitly.
        """
        raise NotImplementedError
