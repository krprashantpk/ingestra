"""Asynchronous text embeddings using Azure OpenAI."""

from collections.abc import Sequence

from openai import AsyncAzureOpenAI, omit

from .base import BaseEmbeddings


class AzureOpenAIEmbeddings(BaseEmbeddings):
    """Generate vectors using a caller-owned async Azure OpenAI client.

    ``deployment_name`` is the Azure deployment name, not the underlying model
    name. Optional ``dimensions`` requires a model that supports this setting.
    Authentication, retries, timeouts, and cleanup belong to the supplied client.
    """

    def __init__(
        self,
        client: AsyncAzureOpenAI,
        deployment_name: str,
        *,
        dimensions: int | None = None,
    ) -> None:
        if not isinstance(deployment_name, str):
            raise TypeError("deployment_name must be a string")
        if not deployment_name.strip():
            raise ValueError("deployment_name must not be blank")
        if dimensions is not None:
            if isinstance(dimensions, bool) or not isinstance(dimensions, int):
                raise TypeError("dimensions must be a positive integer")
            if dimensions <= 0:
                raise ValueError("dimensions must be a positive integer")

        self._client = client
        self._deployment_name = deployment_name
        self._dimensions = dimensions

    async def generate(self, texts: Sequence[str]) -> list[list[float]]:
        """Return one embedding per input, preserving input order.

        A single call sends at most 2,048 nonblank texts in one SDK request.
        Empty input returns an empty list without a request. Inputs are never
        truncated; callers must respect model and aggregate token limits.
        Invalid input raises ``TypeError`` or ``ValueError``. Incomplete or
        incorrectly indexed responses raise ``RuntimeError``; SDK errors
        propagate unchanged.
        """
        if isinstance(texts, (str, bytes)) or not isinstance(texts, Sequence):
            raise TypeError("texts must be a sequence of strings, not a single string")
        inputs = list(texts)
        if len(inputs) > 2048:
            raise ValueError("texts must contain at most 2,048 inputs per request")
        for index, text in enumerate(inputs):
            if not isinstance(text, str):
                raise TypeError(f"texts[{index}] must be a string")
            if not text.strip():
                raise ValueError(f"texts[{index}] must not be blank")
        if not inputs:
            return []

        response = await self._client.embeddings.create(
            input=inputs,
            model=self._deployment_name,
            dimensions=self._dimensions if self._dimensions is not None else omit,
            encoding_format="float",
        )
        ordered = sorted(response.data, key=lambda item: item.index)
        if [item.index for item in ordered] != list(range(len(inputs))):
            raise RuntimeError(
                "Azure OpenAI returned invalid embedding indices; "
                "expected exactly one embedding per input"
            )
        return [item.embedding for item in ordered]
