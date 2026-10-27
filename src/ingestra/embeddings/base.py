"""Provider-independent interface for asynchronous embedding generation."""

from abc import ABC, abstractmethod
from collections.abc import Sequence


class BaseEmbeddings(ABC):
    """Common interface for interchangeable embedding providers.

    Applications depend on this type while callers select and configure a
    concrete provider. Client construction and resource ownership remain
    provider-specific.
    """

    @abstractmethod
    async def generate(self, texts: Sequence[str]) -> list[list[float]]:
        """Return one vector per nonblank input string, in input order.

        Empty input returns an empty list. Implementations must not silently
        truncate inputs or discard results. Invalid inputs and provider errors
        must raise explicitly; provider-specific limits may also apply.
        """
        raise NotImplementedError
