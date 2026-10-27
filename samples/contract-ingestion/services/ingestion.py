"""Convert, embed, and atomically replace document metadata and SQL chunks."""

import logging
import os
from datetime import UTC, datetime
from hashlib import sha256
from itertools import count

from azure.ai.contentunderstanding.aio import ContentUnderstandingClient
from azure.identity.aio import DefaultAzureCredential, get_bearer_token_provider
from openai import AsyncAzureOpenAI
from sqlalchemy import delete

from ingestra.chunker import MarkdownTokenChunker
from ingestra.converter import AzureContentUnderstandingConverter
from ingestra.embeddings import AzureOpenAIEmbeddings
from ingestra.pipeline import Pipeline
from ingestra.store import AzureSQLStore
from ingestra.types import EmbeddedChunk

from utilities.database import EMBEDDING_DIMENSIONS, chunks, create_sql_engine, documents

logger = logging.getLogger(__name__)
MAX_FILE_BYTES = 20 * 1024 * 1024


class EmptyExtractionError(RuntimeError):
    """Indicate that a file produced no usable Markdown chunks."""


def validate_file(data: bytes, filename: str) -> None:
    """Reject missing filenames, empty bodies, and oversized uploads."""
    if not filename.strip() or len(filename) > 1024:
        raise ValueError("Supply a nonblank filename of at most 1024 characters")
    if not data:
        raise ValueError("The uploaded file is empty")
    if len(data) > MAX_FILE_BYTES:
        raise ValueError(f"Files must not exceed {MAX_FILE_BYTES} bytes")


async def ingest_file(data: bytes, filename: str, source: str) -> dict[str, object]:
    """Ingest through the pipeline and commit both SQL tables together.

    Args:
        data: Raw file bytes, limited to 20 MiB in this sample.
        filename: Display filename supplied by the caller or blob binding.
        source: Stable source identity used to replace earlier ingestion.

    Returns:
        Document identity and chunk count after the SQL transaction commits.

    Raises:
        ValueError: The upload fails sample input validation.
        EmptyExtractionError: The analyzer produced no usable chunks and SQL changes were rolled back.
    """
    validate_file(data, filename)
    logger.info("Starting ingestion for source '%s' with %d bytes", source, len(data))
    document_id = sha256(source.encode("utf-8")).hexdigest()
    indices = count()

    def map_metadata(metadata: dict[str, object]) -> dict[str, object]:
        """Map extracted fields and provenance into the document row."""
        return {
            "document_id": document_id,
            "filename": filename,
            "source": source,
            "content_sha256": sha256(data).hexdigest(),
            "content_bytes": len(data),
            "ingested_at": datetime.now(UTC),
            "extracted_metadata": metadata,
        }

    def map_chunk(chunk: EmbeddedChunk) -> dict[str, object]:
        """Assign a stable ordered chunk identity and preserve source pages."""
        index = next(indices)
        return {
            "id": f"{document_id}:{index}",
            "document_id": document_id,
            "chunk_index": index,
            "original_text": chunk.original_text,
            "embedding_text": chunk.embedding_text,
            "embedding": chunk.embedding,
            "page_numbers": list(chunk.page_numbers),
        }

    async with DefaultAzureCredential() as credential:
        async with (
            ContentUnderstandingClient(os.environ["AZURE_CONTENT_UNDERSTANDING_ENDPOINT"], credential, api_version=os.environ.get("AZURE_CONTENT_UNDERSTANDING_API_VERSION", "2025-11-01")) as client,
            AsyncAzureOpenAI(
                azure_endpoint=os.environ["AZURE_OPENAI_ENDPOINT"],
                api_version="2024-10-21",
                azure_ad_token_provider=get_bearer_token_provider(credential, "https://cognitiveservices.azure.com/.default"),
            ) as openai_client,
        ):
            token = await credential.get_token("https://database.windows.net/.default")
            engine = create_sql_engine(os.environ["AZURE_SQL_SERVER"], os.environ["AZURE_SQL_DATABASE"], token.token)
            try:
                async with engine.begin() as connection:
                    pipeline = Pipeline(
                        AzureContentUnderstandingConverter(client, os.environ.get("AZURE_CONTENT_UNDERSTANDING_ANALYZER", "prebuilt-documentSearch")),
                        MarkdownTokenChunker(chunk_size=2048),
                        AzureOpenAIEmbeddings(openai_client, os.environ.get("AZURE_OPENAI_EMBEDDING_DEPLOYMENT", "text-embedding-3-small"), dimensions=EMBEDDING_DIMENSIONS),
                        markdown_store=AzureSQLStore(connection, chunks),
                        metadata_store=AzureSQLStore(connection, documents),
                    )
                    markdown, metadata = await pipeline.convert(data)
                    embedded_chunks = await pipeline.chunk(markdown)
                    await pipeline.ingest_metadata(metadata, metadata_mapper=map_metadata)
                    if not embedded_chunks:
                        raise EmptyExtractionError("The analyzer returned no usable chunks; check the file format and analyzer")
                    await pipeline.ingest_chunks(embedded_chunks, chunk_mapper=map_chunk)
                    # The pipeline's metadata upsert holds the document lock until commit.
                    await connection.execute(delete(chunks).where(chunks.c.document_id == document_id, chunks.c.chunk_index >= len(embedded_chunks)))
            finally:
                await engine.dispose()
    logger.info("Completed ingestion for source '%s' with %d chunks", source, len(embedded_chunks))
    return {"document_id": document_id, "filename": filename, "chunks": len(embedded_chunks)}
