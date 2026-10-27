"""Tests for async Azure OpenAI embeddings without service requests."""

import json
import unittest

import httpx
from openai import AsyncAzureOpenAI, AuthenticationError, RateLimitError

from ingestra.embeddings import AzureOpenAIEmbeddings, BaseEmbeddings


class AzureOpenAIEmbeddingsTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        self.requests: list[httpx.Request] = []
        self.status_code = 200
        self.payload: dict[str, object] = {}
        self._set_embeddings([0, 1])
        self.client = AsyncAzureOpenAI(
            azure_endpoint="https://example.openai.azure.com",
            api_version="2024-10-21",
            api_key="test-key",
            max_retries=0,
            http_client=httpx.AsyncClient(
                transport=httpx.MockTransport(self._respond),
            ),
        )
        self.addAsyncCleanup(self.client.close)
        self.embeddings: BaseEmbeddings = AzureOpenAIEmbeddings(
            self.client, "test-embedding-deployment"
        )

    def _set_embeddings(self, indices: list[int]) -> None:
        self.payload = {
            "object": "list",
            "model": "text-embedding-3-small",
            "data": [
                {
                    "object": "embedding",
                    "index": index,
                    "embedding": [float(index), index + 0.5],
                }
                for index in indices
            ],
            "usage": {"prompt_tokens": 8, "total_tokens": 8},
        }

    def _respond(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        return httpx.Response(self.status_code, json=self.payload)

    async def test_sends_async_sdk_request_without_changing_text(self) -> None:
        texts = ["  # First\n\nDocument text.  ", "Second document"]

        vectors = await self.embeddings.generate(texts)

        self.assertEqual(vectors, [[0.0, 0.5], [1.0, 1.5]])
        self.assertEqual(len(self.requests), 1)
        request = self.requests[0]
        self.assertEqual(request.method, "POST")
        self.assertEqual(
            request.url.path,
            "/openai/deployments/test-embedding-deployment/embeddings",
        )
        self.assertEqual(request.url.params["api-version"], "2024-10-21")
        self.assertEqual(
            json.loads(request.content),
            {
                "input": texts,
                "model": "test-embedding-deployment",
                "encoding_format": "float",
            },
        )
        self.assertFalse(self.client.is_closed())

    async def test_returns_vectors_in_input_order(self) -> None:
        self._set_embeddings([1, 0])

        vectors = await self.embeddings.generate(["first", "second"])

        self.assertEqual(vectors, [[0.0, 0.5], [1.0, 1.5]])

    async def test_single_text_sequence_retains_nested_result_shape(self) -> None:
        self._set_embeddings([0])

        vectors = await self.embeddings.generate(("one text",))

        self.assertEqual(vectors, [[0.0, 0.5]])
        self.assertEqual(json.loads(self.requests[0].content)["input"], ["one text"])

    async def test_dimensions_are_forwarded_when_configured(self) -> None:
        embeddings = AzureOpenAIEmbeddings(self.client, "test-deployment", dimensions=2)

        await embeddings.generate(["first", "second"])

        self.assertEqual(json.loads(self.requests[0].content)["dimensions"], 2)

    async def test_empty_input_does_not_make_a_request(self) -> None:
        self.assertEqual(await self.embeddings.generate([]), [])
        self.assertEqual(self.requests, [])

    async def test_rejects_non_sequence_or_single_string_inputs(self) -> None:
        for texts in ("single text", b"bytes", None, 123, iter(["text"])):
            with self.subTest(texts=texts):
                with self.assertRaises(TypeError):
                    await self.embeddings.generate(texts)
        self.assertEqual(self.requests, [])

    async def test_validates_all_texts_before_making_a_request(self) -> None:
        for text in ("", " \t\n", None, 123, b"bytes"):
            with self.subTest(text=text):
                expected = ValueError if isinstance(text, str) else TypeError
                with self.assertRaisesRegex(expected, r"texts\[1\]"):
                    await self.embeddings.generate(["valid", text])
        self.assertEqual(self.requests, [])

    async def test_accepts_the_maximum_number_of_inputs(self) -> None:
        self._set_embeddings(list(range(2048)))

        vectors = await self.embeddings.generate(["text"] * 2048)

        self.assertEqual(len(vectors), 2048)
        self.assertEqual(len(self.requests), 1)
        self.assertEqual(len(json.loads(self.requests[0].content)["input"]), 2048)

    async def test_rejects_too_many_inputs_without_a_request(self) -> None:
        with self.assertRaisesRegex(ValueError, "2,048"):
            await self.embeddings.generate(["text"] * 2049)
        self.assertEqual(self.requests, [])

    async def test_rejects_missing_duplicate_or_out_of_range_indices(self) -> None:
        for indices in ([], [0], [0, 0], [0, 2], [-1, 0], [0, 1, 2]):
            with self.subTest(indices=indices):
                self._set_embeddings(indices)
                with self.assertRaisesRegex(RuntimeError, "exactly one embedding"):
                    await self.embeddings.generate(["first", "second"])

    async def test_service_errors_propagate(self) -> None:
        for status_code, error_type in (
            (401, AuthenticationError),
            (429, RateLimitError),
        ):
            with self.subTest(status_code=status_code):
                self.status_code = status_code
                self.payload = {
                    "error": {"message": "service failure", "code": "test-error"}
                }
                with self.assertRaises(error_type):
                    await self.embeddings.generate(["text"])

    async def test_supplied_client_can_be_reused(self) -> None:
        self._set_embeddings([0])

        await self.embeddings.generate(["first"])
        await self.embeddings.generate(["second"])

        self.assertEqual(len(self.requests), 2)
        self.assertFalse(self.client.is_closed())

    def test_deployment_name_must_be_a_nonblank_string(self) -> None:
        for deployment_name in ("", " \t", None, 123):
            with self.subTest(deployment_name=deployment_name):
                expected = ValueError if isinstance(deployment_name, str) else TypeError
                with self.assertRaises(expected):
                    AzureOpenAIEmbeddings(self.client, deployment_name)

    def test_dimensions_must_be_a_positive_integer(self) -> None:
        for dimensions in (0, -1, True, False, 1.5, "2"):
            with self.subTest(dimensions=dimensions):
                expected = (
                    ValueError
                    if isinstance(dimensions, int) and not isinstance(dimensions, bool)
                    else TypeError
                )
                with self.assertRaises(expected):
                    AzureOpenAIEmbeddings(self.client, "deployment", dimensions=dimensions)


if __name__ == "__main__":
    unittest.main()
