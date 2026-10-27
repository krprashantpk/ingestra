"""Define shared SQL tables and encrypted, token-authenticated connections."""

import struct

from sqlalchemy import JSON, BigInteger, Column, DateTime, ForeignKey, Integer, MetaData, String, Table, UnicodeText
from sqlalchemy.engine import URL
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine
from sqlalchemy.pool import NullPool

from ingestra.store import AzureSQLVector

EMBEDDING_DIMENSIONS = 1536
schema = MetaData()
documents = Table(
    "document_metadata",
    schema,
    Column("document_id", String(64), primary_key=True),
    Column("filename", UnicodeText, nullable=False),
    Column("source", UnicodeText, nullable=False),
    Column("content_sha256", String(64), nullable=False),
    Column("content_bytes", BigInteger, nullable=False),
    Column("ingested_at", DateTime(timezone=True), nullable=False),
    Column("extracted_metadata", JSON, nullable=False),
    schema="dbo",
)
chunks = Table(
    "document_chunks",
    schema,
    Column("id", String(80), primary_key=True),
    Column("document_id", String(64), ForeignKey("dbo.document_metadata.document_id"), nullable=False, index=True),
    Column("chunk_index", Integer, nullable=False),
    Column("original_text", UnicodeText, nullable=False),
    Column("embedding_text", UnicodeText, nullable=False),
    Column("embedding", AzureSQLVector(EMBEDDING_DIMENSIONS), nullable=False),
    Column("page_numbers", JSON, nullable=False),
    schema="dbo",
)


def create_sql_engine(server: str, database: str, access_token: str) -> AsyncEngine:
    """Create a short-lived SQL engine using an Entra access token.

    Args:
        server: Azure SQL server fully qualified domain name.
        database: Target database name.
        access_token: Token for the Azure SQL resource.

    Returns:
        Caller-owned asynchronous engine requiring Microsoft ODBC Driver 18.
    """
    token_bytes = access_token.encode("utf-16-le")
    token = struct.pack(f"<I{len(token_bytes)}s", len(token_bytes), token_bytes)
    connection_string = f"Driver={{ODBC Driver 18 for SQL Server}};Server=tcp:{server},1433;Database={database};Encrypt=yes;TrustServerCertificate=no;LongAsMax=Yes;Connection Timeout=30;"
    return create_async_engine(URL.create("mssql+aioodbc", query={"odbc_connect": connection_string}), connect_args={"attrs_before": {1256: token}}, poolclass=NullPool)
