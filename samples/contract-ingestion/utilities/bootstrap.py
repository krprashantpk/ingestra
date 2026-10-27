"""Initialize the sample's SQL tables and Function SQL user without modifying AI services."""

import argparse
import asyncio
import logging
from uuid import UUID

from azure.identity.aio import AzureCliCredential
from sqlalchemy import text

from .database import create_sql_engine, schema

logger = logging.getLogger(__name__)


async def initialize(args: argparse.Namespace) -> None:
    """Create SQL tables and grant the Function client ID table-scoped DML permissions."""
    async with AzureCliCredential() as credential:
        logger.info("Initializing SQL database '%s' on server '%s'", args.database, args.sql_server)
        token = await credential.get_token("https://database.windows.net/.default")
        engine = create_sql_engine(args.sql_server, args.database, token.token)
        sid = UUID(args.client_id).bytes_le.hex()
        try:
            async with engine.begin() as connection:
                await connection.run_sync(schema.create_all)
                # A validated UUID SID avoids a Microsoft Graph directory lookup.
                await connection.execute(text(f"""
                    IF NOT EXISTS (SELECT 1 FROM sys.database_principals WHERE name = N'ingestra-function')
                        CREATE USER [ingestra-function] WITH SID = 0x{sid}, TYPE = E;
                    IF NOT EXISTS (SELECT 1 FROM sys.database_principals WHERE name = N'ingestra-function' AND sid = 0x{sid})
                        THROW 50000, 'The existing ingestra-function user belongs to another identity.', 1;
                    GRANT SELECT, INSERT, UPDATE, DELETE ON OBJECT::dbo.document_metadata TO [ingestra-function];
                    GRANT SELECT, INSERT, UPDATE, DELETE ON OBJECT::dbo.document_chunks TO [ingestra-function];
                """))
        finally:
            await engine.dispose()
        logger.info("Initialized SQL database '%s' with two tables and Function DML permissions", args.database)


def main() -> None:
    """Parse deployment outputs and initialize only the SQL data plane."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sql-server", required=True)
    parser.add_argument("--database", required=True)
    parser.add_argument("--client-id", required=True, type=UUID, help="Application (client) ID of the Function managed identity, not its object ID")
    args = parser.parse_args()
    args.client_id = str(args.client_id)
    logging.basicConfig(level=logging.INFO)
    asyncio.run(initialize(args))


if __name__ == "__main__":
    main()
