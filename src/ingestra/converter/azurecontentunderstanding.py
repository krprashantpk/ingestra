"""Asynchronous Markdown and metadata conversion using Azure Content Understanding."""

import datetime
import logging

from azure.ai.contentunderstanding import to_llm_input
from azure.ai.contentunderstanding.aio import ContentUnderstandingClient
from azure.ai.contentunderstanding.models import AnalysisResult

from .base import BaseConverter

logger = logging.getLogger(__name__)


def _to_str(val: object) -> object:
    """Convert date/datetime to ISO string, pass through strings/None."""
    if isinstance(val, (datetime.date, datetime.datetime)):
        return val.isoformat()
    return val


def _extract_field_value(field: object) -> object:
    """Recursively extract a field's value based on its type."""
    if field is None:
        return None

    # Handle plain dicts (e.g. inside valueObject)
    if isinstance(field, dict):
        if "valueObject" in field:
            return {k: _extract_field_value(v) for k, v in field["valueObject"].items()}
        if "valueArray" in field:
            return [_extract_field_value(item) for item in field["valueArray"]]
        for key in ("valueString", "valueDate", "valueNumber", "valueInteger", "valueBoolean"):
            if key in field:
                return _to_str(field[key])
        return field.get("value")

    # Handle SDK model objects
    if hasattr(field, "value_object") and field.value_object is not None:
        return {k: _extract_field_value(v) for k, v in field.value_object.items()}
    if hasattr(field, "value_array") and field.value_array is not None:
        return [_extract_field_value(item) for item in field.value_array]

    # Scalar SDK field
    for attr in ("value_string", "value_date", "value_number", "value_integer", "value_boolean"):
        val = getattr(field, attr, None)
        if val is not None:
            return _to_str(val)
    if hasattr(field, "value"):
        return _to_str(field.value)

    return _to_str(field)


class AzureContentUnderstandingConverter(BaseConverter):
    """Convert bytes using a caller-owned async Content Understanding client.

    Only the first content item supplies SDK-formatted Markdown and flattened
    field metadata. The SDK formatter adds front matter and document page markers.
    Authentication, retries, timeouts, and cleanup belong to the supplied client.
    """

    def __init__(
        self, cu_client: ContentUnderstandingClient, analyzer_id: str
    ) -> None:
        if not isinstance(analyzer_id, str):
            raise TypeError("analyzer_id must be a string")
        if not analyzer_id.strip():
            raise ValueError("analyzer_id must not be blank")

        self._cu_client = cu_client
        self._analyzer_id = analyzer_id

    async def convert(self, data: bytes) -> tuple[str, dict[str, object]]:
        """Return SDK-formatted first-content Markdown and flattened fields.

        Missing contents return empty Markdown and metadata with a warning.
        Missing or whitespace-only Markdown on the first item becomes an empty string
        with a warning, never Markdown from a later item. Extracted fields are
        returned separately rather than duplicated in the formatted Markdown.
        SDK, polling, and formatting errors propagate unchanged.

        Args:
            data: Source document bytes passed to the configured analyzer.

        Returns:
            SDK-formatted Markdown with page markers and flattened first-content fields as metadata.

        Raises:
            TypeError: The input is not bytes.
        """
        if not isinstance(data, bytes):
            raise TypeError("data must be bytes")

        logger.info("Begin CU extraction with analyzer '%s'", self._analyzer_id)
        poller = await self._cu_client.begin_analyze_binary(
            analyzer_id=self._analyzer_id,
            binary_input=data,
            content_type="application/octet-stream",
        )
        result = await poller.result()
        if not result.contents:
            logger.warning("CU analyzer '%s' returned no content", self._analyzer_id)
            return "", {}

        content = result.contents[0]
        markdown = content.markdown
        if markdown is None:
            logger.warning(
                "CU analyzer '%s' returned no Markdown for the first content item",
                self._analyzer_id,
            )
            markdown = ""
        elif not markdown.strip():
            logger.warning("CU analyzer '%s' returned blank Markdown for the first content item", self._analyzer_id)
            markdown = ""
        else:
            markdown = to_llm_input(AnalysisResult(contents=[content], warnings=result.warnings), include_fields=False)
        field_schemas = {
            field_name: _extract_field_value(field_obj)
            for field_name, field_obj in (content.fields or {}).items()
        }

        logger.info("Completed CU extraction - fields: %s", list(field_schemas.keys()))
        return markdown, field_schemas
