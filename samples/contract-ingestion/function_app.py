"""Accept raw HTTP uploads and Event Grid blob notifications for ingestion."""

import json
import logging

import azure.functions as func
from azure.core.exceptions import AzureError
from openai import OpenAIError
from sqlalchemy.exc import SQLAlchemyError

from services.ingestion import MAX_FILE_BYTES, EmptyExtractionError, ingest_file, validate_file

logger = logging.getLogger(__name__)
app = func.FunctionApp(http_auth_level=func.AuthLevel.FUNCTION)


@app.function_name(name="IngestHttp")
@app.route(route="ingest", methods=["POST"])
async def ingest_http(req: func.HttpRequest) -> func.HttpResponse:
    """Ingest a raw request body named by the filename query parameter."""
    filename = req.params.get("filename", "")
    data = req.get_body()
    try:
        validate_file(data, filename)
    except ValueError as error:
        logger.warning("Rejected HTTP upload '%s': %s", filename, error)
        return func.HttpResponse(json.dumps({"error": str(error)}), status_code=413 if len(data) > MAX_FILE_BYTES else 400, mimetype="application/json")

    try:
        result = await ingest_file(data, filename, f"http:{filename}")
    except EmptyExtractionError as error:
        logger.warning("No usable content in HTTP upload '%s': %s", filename, error)
        return func.HttpResponse(json.dumps({"error": str(error)}), status_code=422, mimetype="application/json")
    except (AzureError, OpenAIError, SQLAlchemyError):
        logger.exception("Provider failed while ingesting HTTP upload '%s'", filename)
        return func.HttpResponse(json.dumps({"error": "Ingestion failed; see Application Insights for details."}), status_code=502, mimetype="application/json")
    return func.HttpResponse(json.dumps(result), status_code=200, mimetype="application/json")


@app.function_name(name="DiagnoseIngestion")
@app.route(route="diagnose-ingestion", methods=["GET"])
async def diagnose_ingestion(req: func.HttpRequest) -> func.HttpResponse:
    """Temporarily inspect provider prerequisites without processing a document."""
    import base64
    import os

    import pyodbc
    from azure.ai.contentunderstanding.aio import ContentUnderstandingClient
    from azure.identity.aio import DefaultAzureCredential
    from sqlalchemy import text

    from utilities.database import create_sql_engine

    result: dict[str, object] = {"odbc_drivers": pyodbc.drivers(), "stage": "sql"}
    try:
        async with DefaultAzureCredential() as credential:
            token = await credential.get_token("https://database.windows.net/.default")
            claims = json.loads(base64.urlsafe_b64decode(token.token.split(".")[1] + "=="))
            result["token_identity"] = {name: claims.get(name) for name in ("oid", "appid", "tid", "aud")}
            engine = create_sql_engine(os.environ["AZURE_SQL_SERVER"], os.environ["AZURE_SQL_DATABASE"], token.token)
            try:
                async with engine.connect() as connection:
                    result["sql_connected"] = await connection.scalar(text("SELECT 1")) == 1
            finally:
                await engine.dispose()
            result["stage"] = "analyzer"
            async with ContentUnderstandingClient(os.environ["AZURE_CONTENT_UNDERSTANDING_ENDPOINT"], credential, api_version=os.environ.get("AZURE_CONTENT_UNDERSTANDING_API_VERSION", "2025-11-01")) as client:
                analyzer = await client.get_analyzer(os.environ["AZURE_CONTENT_UNDERSTANDING_ANALYZER"])
                result["analyzer_status"] = str(analyzer.status)
            result["stage"] = "complete"
    except (AzureError, SQLAlchemyError) as error:
        result["error_type"] = type(error).__name__
        result["status_code"] = getattr(error, "status_code", None)
        original = getattr(error, "orig", None)
        if original is not None:
            result["connection_error"] = list(original.args)
    return func.HttpResponse(json.dumps(result), mimetype="application/json")


@app.function_name(name="IngestBlob")
@app.blob_trigger(arg_name="blob", path="%INGEST_CONTAINER%/{name}", connection="IngestStorage", source="EventGrid")
async def ingest_blob(blob: func.InputStream) -> None:
    """Ingest an uploaded blob, letting failures propagate for host retries."""
    source = blob.name
    if source is None:
        raise ValueError("The blob binding did not supply a source name")
    if blob.length is not None and blob.length > MAX_FILE_BYTES:
        logger.error("Blob '%s' exceeds the %d-byte sample limit", source, MAX_FILE_BYTES)
        raise ValueError(f"Files must not exceed {MAX_FILE_BYTES} bytes")
    data = blob.read(size=MAX_FILE_BYTES + 1)
    filename = source.rsplit("/", 1)[-1]
    try:
        validate_file(data, filename)
        await ingest_file(data, filename, f"blob:{source}")
    except (ValueError, EmptyExtractionError, AzureError, OpenAIError, SQLAlchemyError):
        logger.exception("Failed to ingest blob '%s'; allowing the host to retry", source)
        raise
