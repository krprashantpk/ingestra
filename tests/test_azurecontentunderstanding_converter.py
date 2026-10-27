"""Tests for first-content conversion without Azure requests."""

import inspect
import unittest
from typing import get_type_hints
from unittest.mock import AsyncMock, Mock, patch

from azure.ai.contentunderstanding.aio import ContentUnderstandingClient
from azure.ai.contentunderstanding.models import AnalysisResult
from azure.core.exceptions import HttpResponseError

from ingestra.chunker import MarkdownTokenChunker
from ingestra.converter import AzureContentUnderstandingConverter, BaseConverter
from ingestra.converter.azurecontentunderstanding import (
    AzureContentUnderstandingConverter as ModuleConverter,
)


MODULE = "ingestra.converter.azurecontentunderstanding"


class ContentUnderstandingConverterTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        self.poller = Mock()
        self.poller.result = AsyncMock()
        self.sdk = Mock(spec=ContentUnderstandingClient)
        self.sdk.begin_analyze_binary = AsyncMock(return_value=self.poller)
        self.converter = AzureContentUnderstandingConverter(self.sdk, "test-analyzer")

    def test_exported_converter_implements_the_interface(self) -> None:
        self.assertIs(AzureContentUnderstandingConverter, ModuleConverter)
        self.assertIsInstance(self.converter, BaseConverter)
        self.assertFalse(inspect.isabstract(AzureContentUnderstandingConverter))
        self.assertEqual(
            get_type_hints(AzureContentUnderstandingConverter.convert),
            get_type_hints(BaseConverter.convert),
        )

    def test_rejects_invalid_analyzer_ids(self) -> None:
        for analyzer_id in (None, 123):
            with self.subTest(analyzer_id=analyzer_id):
                with self.assertRaisesRegex(TypeError, "analyzer_id must be a string"):
                    AzureContentUnderstandingConverter(self.sdk, analyzer_id)
        for analyzer_id in ("", " \t\n"):
            with self.subTest(analyzer_id=analyzer_id):
                with self.assertRaisesRegex(ValueError, "analyzer_id must not be blank"):
                    AzureContentUnderstandingConverter(self.sdk, analyzer_id)
        self.sdk.begin_analyze_binary.assert_not_called()

    async def test_returns_only_first_content_fields_and_markdown(self) -> None:
        self.poller.result.return_value = AnalysisResult(
            {
                "contents": [
                    {
                        "kind": "document",
                        "markdown": "# First",
                        "fields": {
                            "Total": {"type": "number", "valueNumber": 0},
                            "Approved": {"type": "boolean", "valueBoolean": False},
                            "DueDate": {"type": "date", "valueDate": "2026-10-21"},
                            "Empty": {"type": "string", "valueString": ""},
                            "Missing": {"type": "string"},
                            "Items": {
                                "type": "array",
                                "valueArray": [
                                    {
                                        "type": "object",
                                        "valueObject": {
                                            "Name": {
                                                "type": "string",
                                                "valueString": "First item",
                                            }
                                        },
                                    }
                                ],
                            },
                        },
                    },
                    {
                        "kind": "document",
                        "markdown": "# Second",
                        "fields": {
                            "Total": {"type": "number", "valueNumber": 99},
                            "Items": {
                                "type": "array",
                                "valueArray": [
                                    {"type": "string", "valueString": "Second item"}
                                ],
                            },
                            "SecondOnly": {"type": "string", "valueString": "Ignore"},
                        },
                    },
                ]
            }
        )

        converter: BaseConverter = self.converter
        result = await converter.convert(b"document")

        self.assertEqual(
            result,
            (
                "---\nmimeType: unknown\n---\n<!-- InputPageNumber: 1 -->\n\n# First",
                {
                    "Total": 0,
                    "Approved": False,
                    "DueDate": "2026-10-21",
                    "Empty": "",
                    "Missing": None,
                    "Items": [{"Name": "First item"}],
                },
            ),
        )
        self.sdk.begin_analyze_binary.assert_awaited_once_with(
            analyzer_id="test-analyzer",
            binary_input=b"document",
            content_type="application/octet-stream",
        )
        self.poller.result.assert_awaited_once_with()
        self.assertEqual(len(self.poller.result.return_value.contents), 2)

    async def test_page_spans_supply_original_page_numbers_to_chunker(self) -> None:
        """Use SDK page spans rather than assuming consecutive page numbers."""
        first_page = "# First\n\nFirst page.\n\n"
        second_page = "# Second\n\nSecond page."
        self.poller.result.return_value = AnalysisResult(
            {
                "contents": [
                    {
                        "kind": "document",
                        "mimeType": "application/pdf",
                        "markdown": first_page + second_page,
                        "pages": [
                            {"pageNumber": 3, "spans": [{"offset": 0, "length": len(first_page)}]},
                            {"pageNumber": 5, "spans": [{"offset": len(first_page), "length": len(second_page)}]},
                        ],
                        "fields": {"Total": {"type": "number", "valueNumber": 10}},
                    }
                ]
            }
        )

        markdown, field_schemas = await self.converter.convert(b"document")
        chunks = MarkdownTokenChunker(chunk_size=200, tokenizer=len).chunk(markdown)

        self.assertTrue(markdown.startswith("---\nmimeType: application/pdf\n"))
        self.assertIn("<!-- InputPageNumber: 3 -->\n\n" + first_page, markdown)
        self.assertIn("<!-- InputPageNumber: 5 -->\n\n" + second_page, markdown)
        self.assertNotIn("fields:", markdown)
        self.assertNotIn("Total:", markdown)
        self.assertEqual(field_schemas, {"Total": 10})
        self.assertEqual("".join(chunk.original_text for chunk in chunks), markdown)
        self.assertEqual({page for chunk in chunks for page in chunk.page_numbers}, {3, 5})
        for chunk in chunks:
            self.assertEqual(chunk.token_count, len(chunk.embedding_text))
            self.assertLessEqual(chunk.token_count, 200)

    async def test_page_breaks_are_formatted_as_page_markers(self) -> None:
        """Retain the source document's starting page when spans are absent."""
        self.poller.result.return_value = AnalysisResult(
            {
                "contents": [
                    {
                        "kind": "document",
                        "startPageNumber": 4,
                        "endPageNumber": 5,
                        "markdown": "First page.\n\n<!-- PageBreak -->\n\nSecond page.",
                    }
                ]
            }
        )

        markdown, field_schemas = await self.converter.convert(b"document")

        self.assertIn("<!-- InputPageNumber: 4 -->\n\nFirst page.", markdown)
        self.assertIn("<!-- InputPageNumber: 5 -->\n\nSecond page.", markdown)
        self.assertNotIn("<!-- PageBreak -->", markdown)
        self.assertEqual(field_schemas, {})

    async def test_existing_page_markers_are_not_duplicated(self) -> None:
        """Let the SDK preserve already-paginated Markdown."""
        source = "<!-- InputPageNumber: 7 -->\n\n# Existing page"
        self.poller.result.return_value = AnalysisResult({"contents": [{"kind": "document", "markdown": source}]})

        markdown, _ = await self.converter.convert(b"document")

        self.assertEqual(markdown.count("<!-- InputPageNumber:"), 1)
        self.assertTrue(markdown.endswith(source))

    async def test_does_not_fall_back_to_later_content(self) -> None:
        self.poller.result.return_value = AnalysisResult(
            {
                "contents": [
                    {"kind": "document"},
                    {
                        "kind": "document",
                        "markdown": "# Second",
                        "fields": {
                            "Name": {"type": "string", "valueString": "Ignore"}
                        },
                    },
                ]
            }
        )

        with self.assertLogs(MODULE, level="WARNING") as logs:
            result = await self.converter.convert(b"document")

        self.assertEqual(result, ("", {}))
        self.assertIn("no Markdown for the first content item", logs.output[0])

    async def test_empty_or_missing_contents_returns_empty_result_with_warning(self) -> None:
        for payload in ({}, {"contents": []}):
            with self.subTest(payload=payload):
                self.poller.result.return_value = AnalysisResult(payload)

                with self.assertLogs(MODULE, level="WARNING"):
                    result = await self.converter.convert(b"document")

                self.assertEqual(result, ("", {}))

    async def test_missing_markdown_preserves_first_content_metadata(self) -> None:
        self.poller.result.return_value = AnalysisResult(
            {
                "contents": [
                    {
                        "kind": "document",
                        "fields": {"Total": {"type": "number", "valueNumber": 10}},
                    }
                ]
            }
        )

        with self.assertLogs(MODULE, level="WARNING"):
            result = await self.converter.convert(b"document")

        self.assertEqual(result, ("", {"Total": 10}))

    async def test_empty_markdown_does_not_become_front_matter_only(self) -> None:
        """Keep empty Markdown empty while retaining the extracted fields."""
        self.poller.result.return_value = AnalysisResult(
            {
                "contents": [
                    {
                        "kind": "document",
                        "markdown": "",
                        "fields": {"Total": {"type": "number", "valueNumber": 10}},
                    }
                ]
            }
        )

        self.assertEqual(await self.converter.convert(b"document"), ("", {"Total": 10}))

    async def test_given_whitespace_markdown_when_converting_then_returns_empty_text_and_fields(self) -> None:
        """Do not turn blank extraction into an embeddable metadata-only document."""
        for markdown in (" ", "\t\r\n", "\u00a0\n"):
            with self.subTest(markdown=markdown):
                self.poller.result.return_value = AnalysisResult({"contents": [{"kind": "document", "markdown": markdown, "fields": {"Total": {"type": "number", "valueNumber": 10}}}]})

                with self.assertLogs(MODULE, level="WARNING"):
                    result = await self.converter.convert(b"document")

                self.assertEqual(result, ("", {"Total": 10}))
                self.assertEqual(MarkdownTokenChunker(tokenizer=len).chunk(result[0]), [])

    async def test_rejects_non_bytes_before_calling_sdk(self) -> None:
        for data in (None, "document", bytearray(b"document"), memoryview(b"document")):
            with self.subTest(data=data):
                with self.assertRaisesRegex(TypeError, "data must be bytes"):
                    await self.converter.convert(data)
        self.sdk.begin_analyze_binary.assert_not_called()

    async def test_analysis_errors_propagate(self) -> None:
        error = HttpResponseError("analysis failed")
        self.sdk.begin_analyze_binary.side_effect = error

        with self.assertRaises(HttpResponseError) as raised:
            await self.converter.convert(b"document")

        self.assertIs(raised.exception, error)
        self.poller.result.assert_not_awaited()

    async def test_polling_errors_propagate(self) -> None:
        error = HttpResponseError("polling failed")
        self.poller.result.side_effect = error

        with self.assertRaises(HttpResponseError) as raised:
            await self.converter.convert(b"document")

        self.assertIs(raised.exception, error)

    async def test_formatting_errors_propagate(self) -> None:
        """Do not silently return raw Markdown if SDK formatting fails."""
        self.poller.result.return_value = AnalysisResult({"contents": [{"kind": "document", "markdown": "Body."}]})
        error = ValueError("formatting failed")

        with patch(f"{MODULE}.to_llm_input", side_effect=error):
            with self.assertRaises(ValueError) as raised:
                await self.converter.convert(b"document")

        self.assertIs(raised.exception, error)

    async def test_markdown_can_be_chunked_without_changing_metadata(self) -> None:
        self.poller.result.return_value = AnalysisResult(
            {
                "contents": [
                    {
                        "kind": "document",
                        "markdown": "# Invoice\nTotal: 10",
                        "fields": {"Total": {"type": "number", "valueNumber": 10}},
                    }
                ]
            }
        )

        markdown, metadata = await self.converter.convert(b"document")
        chunks = MarkdownTokenChunker(chunk_size=100, tokenizer=len).chunk(markdown)

        self.assertTrue(chunks)
        self.assertEqual("".join(chunk.original_text for chunk in chunks), markdown)
        self.assertEqual({page for chunk in chunks for page in chunk.page_numbers}, {1})
        for chunk in chunks:
            self.assertEqual(chunk.token_count, len(chunk.embedding_text))
            self.assertLessEqual(chunk.token_count, 100)
        self.assertEqual(metadata, {"Total": 10})
        self.sdk.close.assert_not_called()
