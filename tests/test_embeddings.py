"""Tests for the provider-independent embedding interface."""

import inspect
import unittest
from collections.abc import Sequence

from ingestra.embeddings import AzureOpenAIEmbeddings, BaseEmbeddings


class StubEmbeddings(BaseEmbeddings):
    async def generate(self, texts: Sequence[str]) -> list[list[float]]:
        return [[float(len(text))] for text in texts]


class EmbeddingsInterfaceTests(unittest.IsolatedAsyncioTestCase):
    def test_base_class_cannot_be_instantiated(self) -> None:
        self.assertTrue(inspect.isabstract(BaseEmbeddings))
        with self.assertRaises(TypeError):
            BaseEmbeddings()

    def test_subclass_must_implement_generate(self) -> None:
        class IncompleteEmbeddings(BaseEmbeddings):
            pass

        with self.assertRaises(TypeError):
            IncompleteEmbeddings()

    def test_azure_provider_implements_the_interface(self) -> None:
        self.assertTrue(issubclass(AzureOpenAIEmbeddings, BaseEmbeddings))
        self.assertFalse(inspect.isabstract(AzureOpenAIEmbeddings))

    async def test_custom_provider_can_be_used_through_the_interface(self) -> None:
        provider: BaseEmbeddings = StubEmbeddings()

        vectors = await provider.generate(["first", "second"])

        self.assertEqual(vectors, [[5.0], [6.0]])

    async def test_custom_provider_accepts_other_sequences(self) -> None:
        provider: BaseEmbeddings = StubEmbeddings()

        vectors = await provider.generate(("first",))

        self.assertEqual(vectors, [[5.0]])

    async def test_empty_input_retains_the_common_result_shape(self) -> None:
        provider: BaseEmbeddings = StubEmbeddings()

        self.assertEqual(await provider.generate([]), [])


if __name__ == "__main__":
    unittest.main()
