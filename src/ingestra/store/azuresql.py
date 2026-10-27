"""Reusable asynchronous Azure SQL storage with native embedding vectors."""

import json
import logging
import math
from typing import Protocol

from sqlalchemy import Table, and_, cast, select, type_coerce
from sqlalchemy.dialects.mssql import NVARCHAR
from sqlalchemy.engine import Dialect
from sqlalchemy.ext.asyncio import AsyncConnection
from sqlalchemy.sql.elements import BindParameter, Cast, ColumnElement
from sqlalchemy.types import UserDefinedType

from .markdown.base import BaseMarkdownStore
from .metadata.base import BaseMetadataStore

logger = logging.getLogger(__name__)


class _VectorEncoder(Protocol):
    """Preserve SQLAlchemy's named value argument for bind processors."""

    def __call__(self, value: list[float] | None) -> str | None:
        """Encode a vector or preserve a null parameter."""
        ...


class _VectorDecoder(Protocol):
    """Preserve SQLAlchemy's named value argument for result processors."""

    def __call__(self, value: object) -> list[float] | None:
        """Decode a vector result or preserve a null value."""
        ...


class AzureSQLVector(UserDefinedType[list[float]]):
    """Bind Python embeddings to a native Azure SQL float32 VECTOR column."""

    cache_ok = True

    def __init__(self, dimensions: int) -> None:
        """Declare the dimensions of an existing native vector column.

        Args:
            dimensions: Number of float32 elements, between 1 and 1998.

        Raises:
            ValueError: The dimensions are not an integer in the supported range.
        """
        if isinstance(dimensions, bool) or not isinstance(dimensions, int) or not 1 <= dimensions <= 1998:
            raise ValueError("dimensions must be an integer between 1 and 1998")
        self.dimensions = dimensions

    def get_col_spec(self, **kw: object) -> str:
        """Render the native vector type for SQL declarations and casts.

        Args:
            **kw: SQLAlchemy compilation options.

        Returns:
            The SQL vector type declaration.
        """
        return f"VECTOR({self.dimensions})"

    def bind_expression(self, bindvalue: BindParameter[list[float]]) -> Cast[list[float]]:
        """Cast a bound JSON string to the native vector type on the server.

        Args:
            bindvalue: SQLAlchemy parameter carrying the embedding.

        Returns:
            A parameterized vector cast without interpolating vector values.
        """
        return cast(bindvalue, self)

    def column_expression(self, colexpr: ColumnElement[list[float]]) -> ColumnElement[list[float]]:
        """Request JSON text when reading vectors through an ODBC connection.

        Args:
            colexpr: Native vector column selected by SQLAlchemy.

        Returns:
            A text cast retaining this type's vector result processor.
        """
        return type_coerce(cast(colexpr, NVARCHAR()), self)

    def bind_processor(self, dialect: Dialect) -> _VectorEncoder:
        """Serialize valid embeddings for the ODBC driver's string parameters.

        Args:
            dialect: SQLAlchemy dialect requesting the processor.

        Returns:
            A processor that validates and serializes embeddings, preserving nulls.
        """
        def process(value: list[float] | None) -> str | None:
            """Convert an embedding to its SQL vector JSON representation."""
            return None if value is None else json.dumps(self._validate_vector(value), allow_nan=False)

        return process

    def result_processor(self, dialect: Dialect, coltype: object) -> _VectorDecoder:
        """Decode vector JSON returned through the ODBC driver.

        Args:
            dialect: SQLAlchemy dialect requesting the processor.
            coltype: Driver-reported column type.

        Returns:
            A processor returning validated float lists or nulls.
        """
        def process(value: object) -> list[float] | None:
            """Decode a native vector's JSON representation."""
            if value is None:
                return None
            if not isinstance(value, str):
                raise TypeError("vector results must be JSON strings")
            return self._validate_vector(json.loads(value))

        return process

    def _validate_vector(self, value: object) -> list[float]:
        """Validate vector length and finite numeric elements.

        Args:
            value: Candidate embedding supplied by a mapper or the database.

        Returns:
            The validated embedding normalized to floats.

        Raises:
            TypeError: The embedding is not a list of real numbers.
            ValueError: Its dimensions differ or an element is not finite.
        """
        if not isinstance(value, list):
            raise TypeError("an embedding must be a list of numbers")
        if len(value) != self.dimensions:
            raise ValueError(f"expected {self.dimensions} embedding dimensions, received {len(value)}")
        vector: list[float] = []
        for element in value:
            if isinstance(element, bool) or not isinstance(element, (int, float)):
                raise TypeError("embedding elements must be real numbers")
            number = float(element)
            if not math.isfinite(number):
                raise ValueError("embedding elements must be finite")
            vector.append(number)
        return vector


class AzureSQLStore(BaseMarkdownStore, BaseMetadataStore):
    """Upsert chunks or metadata into one existing caller-defined SQL table.

    The caller owns the connection, table schema, and transaction. Use an active
    transaction, such as engine.begin(), and commit it to persist successful
    writes. This store never provisions tables, commits, or closes connections.
    """

    def __init__(self, connection: AsyncConnection, table: Table) -> None:
        """Keep a caller-owned asynchronous connection and table definition.

        Args:
            connection: SQLAlchemy asynchronous SQL Server connection, normally using mssql+aioodbc.
            table: Existing target table with one or more primary-key columns.

        Raises:
            ValueError: The dialect is not SQL Server or the table has no primary key.
        """
        if connection.dialect.name != "mssql":
            raise ValueError("AzureSQLStore requires a SQL Server connection")
        if not table.primary_key.columns:
            raise ValueError("the target table must define a primary key")
        self._connection = connection
        self._table = table
        self._key_names = {column.key for column in table.primary_key.columns}

    async def _store_documents(self, documents: list[dict[str, object]]) -> None:
        """Upsert mapped documents without committing the caller's transaction.

        SQL Server update and serializable-range locks protect the primary-key
        existence check through the following write. All identifiers come from
        SQLAlchemy schema objects and all values use bound parameters.

        Args:
            documents: Complete mapped rows with non-null primary keys.

        Raises:
            ValueError: There is no active transaction, a row has unknown columns, or a primary key is missing.
        """
        if not self._connection.in_transaction():
            raise ValueError("SQL storage requires an active transaction; use engine.begin()")
        columns = set(self._table.columns.keys())
        for document in documents:
            if document.keys() - columns:
                raise ValueError(f"Unknown columns for table {self._table.fullname!r}: {sorted(document.keys() - columns)!r}")
            for key in self._key_names:
                if key not in document or document[key] is None:
                    raise ValueError(f"Each row must include a non-null primary key {key!r}")

        logger.info("Storing %d rows in table '%s'", len(documents), self._table.fullname)
        for document in documents:
            predicate = and_(*(column == document[column.key] for column in self._table.primary_key.columns))
            lookup = select(*self._table.primary_key.columns).where(predicate).with_hint(self._table, "WITH (UPDLOCK, HOLDLOCK)", dialect_name="mssql")
            existing = await self._connection.execute(lookup)
            if existing.first() is None:
                await self._connection.execute(self._table.insert().values(document))
            else:
                updates = {name: value for name, value in document.items() if name not in self._key_names}
                if updates:
                    await self._connection.execute(self._table.update().where(predicate).values(updates))
        logger.info("Stored %d rows in table '%s' in the caller's transaction", len(documents), self._table.fullname)
