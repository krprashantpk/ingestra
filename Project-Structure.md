---
title: Ingestra Project Structure
description: Repository layout, module responsibilities, and sample application.
---

## Index

* [Overview](#overview)
* [Folder Layout](#folder-layout)
* [Root Files and Directories](#root-files-and-directories)
* [Core Package](#core-package)
    * [Conversion Modules](#conversion-modules)
    * [Chunking Modules](#chunking-modules)
    * [Embedding Modules](#embedding-modules)
    * [Storage Modules](#storage-modules)
* [Samples](#samples)
    * [Contract Ingestion](#contract-ingestion)

## Overview

Ingestra is a Python 3.12+ library that turns document bytes into Markdown, splits that Markdown into chunks near a token-size goal, generates embeddings, and optionally persists chunks and extracted metadata. The repository uses a source layout: reusable package code lives under `src/ingestra`, library tests live under `tests`, and a deployable application lives under `samples/contract-ingestion`.

The reusable library defines component contracts and orchestration. Applications supply configured clients, storage schemas, mapping functions, authentication, and resource lifetimes. The sample demonstrates those application responsibilities with Azure Functions and Azure SQL.

## Folder Layout

Generated environments, Python caches, Git internals, and build outputs are omitted. The `.github` directory is shown without expanding its contents.

```text
ingestra/
|-- .github/
|-- .gitignore
|-- AGENTS.md
|-- architecture.md
|-- Project-Structure.md
|-- pyproject.toml
|-- README.md
|-- uv.lock
|-- docs/
|   `-- guide.md
|-- exeperiment/
|   `-- chunkers/
|       |-- markdown_chunking.ipynb
|       `-- samples/
|-- src/
|   `-- ingestra/
|       |-- __init__.py
|       |-- pipeline.py
|       |-- types.py
|       |-- chunker/
|       |   |-- __init__.py
|       |   |-- base.py
|       |   |-- markdown.py
|       |   |-- _structure.py
|       |   `-- _token.py
|       |-- converter/
|       |   |-- __init__.py
|       |   |-- base.py
|       |   `-- azurecontentunderstanding.py
|       |-- embeddings/
|       |   |-- __init__.py
|       |   |-- base.py
|       |   `-- azureopenai.py
|       `-- store/
|           |-- __init__.py
|           |-- azureaisearch.py
|           |-- azuresql.py
|           |-- markdown/
|           |   |-- __init__.py
|           |   `-- base.py
|           `-- metadata/
|               |-- __init__.py
|               `-- base.py
|-- tests/
`-- samples/
    `-- contract-ingestion/
        |-- .funcignore
        |-- Deploy-Sample.ps1
        |-- function_app.py
        |-- host.json
        |-- local.settings.json.example
        |-- README.md
        |-- infra/
        |   |-- main.bicep
        |   |-- events.bicep
        |   |-- foundry-access.bicep
        |   `-- monitoring.bicep
        |-- services/
        |   |-- __init__.py
        |   `-- ingestion.py
        |-- utilities/
        |   |-- __init__.py
        |   |-- bootstrap.py
        |   `-- database.py
        `-- tests/
```

## Root Files and Directories

* [AGENTS.md](AGENTS.md) defines repository conventions for Python environments, dependencies, typing, docstrings, logging, and method formatting.
* [README.md](README.md) provides setup instructions, public component usage, and links to the sample and architecture reference.
* [architecture.md](architecture.md) describes component boundaries and storage flows. Use it alongside the file-oriented descriptions below.
* [Project-Structure.md](Project-Structure.md) catalogs the repository layout and the responsibilities of its modules.
* [pyproject.toml](pyproject.toml) declares package metadata, Python compatibility, runtime dependencies, the `uv_build` build backend, and dependency groups. The `samples` group adds the Azure Functions dependency for the sample.
* [uv.lock](uv.lock) records resolved dependency versions for reproducible environments managed with `uv`.
* [.gitignore](.gitignore) defines files and directories excluded from Git.
* [.github](.github/) holds repository-level GitHub configuration and supporting artifacts, separate from the importable package.
* [docs/guide.md](docs/guide.md) contains configuration, usage examples, component contracts, and local development instructions.
* [exeperiment/chunkers](exeperiment/chunkers/) contains the interactive Markdown chunking notebook and its source samples.

The root `.venv` is a local environment, not source code. Use `uv sync` to synchronize project dependencies and `uv run` to execute tools in that environment.

## Core Package

### Package Entry Point

[src/ingestra/__init__.py](src/ingestra/__init__.py) identifies the package and exposes its version. Feature APIs are organized into their own subpackages; applications import orchestration from `ingestra.pipeline` and providers from the corresponding converter, chunker, embeddings, or store namespace.

### Pipeline Orchestration

[src/ingestra/pipeline.py](src/ingestra/pipeline.py) defines `Pipeline` and re-exports `ChunkResult` and `EmbeddedChunk` for compatibility.

`Pipeline.convert(data)` validates that input is bytes and delegates to the converter, returning Markdown and document-level metadata without chunking, embedding, or storage.

`Pipeline.chunk(markdown)` validates Markdown, chunks the text synchronously, and awaits embedding generation without conversion. It uses each chunk's `embedding_text` when available and falls back to `original_text`. It preserves source order and page numbers, checks vector counts, and returns a `list[EmbeddedChunk]`. Empty chunks skip embedding generation and return an empty list. This method never calls stores.

`Pipeline.ingest_chunks(chunks, *, chunk_mapper)` and `Pipeline.ingest_metadata(metadata, *, metadata_mapper)` persist prepared data independently and return `None`. Each method requires only its matching store and callable mapper, without running conversion, chunking, or embedding. Empty chunk sequences perform no provider writes; empty metadata still produces a mapped document.

Applications compose these methods explicitly: call `convert(data)` and `chunk(markdown)`, then the persistence methods for the configured roles. Write ordering and validation across the complete workflow belong to the application. Applications can construct `ChunkResult(chunks, metadata)` to group processing outputs; the pipeline does not provide a combined ingestion method.

The pipeline does not create clients, provision storage, commit transactions, or guarantee atomicity across storage providers. Component errors propagate; an earlier write may already have succeeded when a later write fails.

### Shared Result Models

[src/ingestra/types.py](src/ingestra/types.py) contains two frozen dataclasses shared by processing and persistence:

* `EmbeddedChunk` contains exact source text in `original_text`, the actual embedding input in `embedding_text`, a numeric `embedding`, and a tuple of source `page_numbers`.
* `ChunkResult` lets applications group embedded chunks in source order with the document-level metadata returned by conversion.

These models are independent of any storage schema. Their dictionaries and lists are not deeply immutable despite the frozen dataclass declarations.

### Conversion Modules

[src/ingestra/converter/__init__.py](src/ingestra/converter/__init__.py) exposes `BaseConverter` and `AzureContentUnderstandingConverter`.

[src/ingestra/converter/base.py](src/ingestra/converter/base.py) defines the abstract asynchronous `convert(data)` contract. Implementations accept bytes and return a tuple containing a Markdown string and a metadata dictionary. This boundary lets the pipeline use different conversion providers without depending on their SDK response types.

[src/ingestra/converter/azurecontentunderstanding.py](src/ingestra/converter/azurecontentunderstanding.py) implements conversion with a caller-owned asynchronous Azure Content Understanding client and a constructor-configured analyzer ID. It formats Markdown from the first content item using the SDK's `to_llm_input` helper, including page markers for downstream attribution. Extracted fields are returned separately as metadata rather than duplicated in the Markdown.

Private helpers recursively extract typed fields, retain nested object and array structure, and convert dates and datetimes to ISO strings. Missing content produces empty output with a warning; missing Markdown retains available fields. Authentication, polling configuration, retries, and client cleanup remain with the caller and supplied SDK client.

### Chunking Modules

[src/ingestra/chunker/__init__.py](src/ingestra/chunker/__init__.py) exposes `BaseChunker`, `Chunk`, and `MarkdownTokenChunker`.

[src/ingestra/chunker/base.py](src/ingestra/chunker/base.py) defines the synchronous `BaseChunker.chunk(text)` interface and the frozen `Chunk` model. A chunk carries `original_text`, optional `embedding_text`, optional `token_count`, and source `page_numbers`. Implementations return chunks in source order, use an empty list for blank input, and reject non-string input.

[src/ingestra/chunker/markdown.py](src/ingestra/chunker/markdown.py) provides the public `MarkdownTokenChunker`. It validates one token-size goal, `chunk_size=2048` by default, and delegates the algorithm to the private modules below. Its default token counter uses the `cl100k_base` encoding from `tiktoken`; callers can supply a compatible counter. `pages_to_markdown()` joins page strings with one-based `InputPageNumber` comments.

[src/ingestra/chunker/_structure.py](src/ingestra/chunker/_structure.py) recognizes Markdown structure without applying token budgets. It tracks source offsets, active headings, paragraphs, fenced code, pipe tables, and HTML table or figure blocks. Private block, unit, and layout models describe preferred split boundaries and repeatable context. HTML parsers identify nested boundaries, table headers, and merged-cell row groups.

[src/ingestra/chunker/_token.py](src/ingestra/chunker/_token.py) packs across blocks near the token-size goal, counting the entire embedding input. Nearby sentence, code-line, and table-row boundaries can take a chunk above the goal. Individually oversized units are recursively refined through finer separators. Only structural context is repeated; prose overlap is not added. The engine also associates source page markers with chunks.

Original text remains in non-overlapping source slices, so joining the slices reconstructs nonblank input. Embedding text may contain added structural context. Oversized content can fall back to character-level splitting rather than silent truncation; those fragments need not remain independently valid Markdown or HTML. Chunking is local and makes no conversion or embedding service requests.

### Embedding Modules

[src/ingestra/embeddings/__init__.py](src/ingestra/embeddings/__init__.py) exposes `BaseEmbeddings` and `AzureOpenAIEmbeddings`.

[src/ingestra/embeddings/base.py](src/ingestra/embeddings/base.py) defines the asynchronous `generate(texts)` interface. Providers accept a sequence of strings and return one numeric vector per input in the same order.

[src/ingestra/embeddings/azureopenai.py](src/ingestra/embeddings/azureopenai.py) implements that interface using a caller-owned `AsyncAzureOpenAI` client. Its configuration includes an Azure deployment name and optional vector dimensions. It rejects blank or invalid inputs and more than 2,048 texts per call, skips SDK requests for empty input, and requests float embeddings. Response indices are validated and reordered to match the input sequence.

This adapter sends one request per nonempty call. It does not automatically split large workloads or truncate text to provider token limits. Client authentication, retries, timeouts, and cleanup remain caller responsibilities.

### Storage Modules

#### Storage Exports and Roles

[src/ingestra/store/__init__.py](src/ingestra/store/__init__.py) exposes `BaseMarkdownStore`, `BaseMetadataStore`, `AzureAISearchStore`, `AzureSQLStore`, and `AzureSQLVector`.

Markdown chunk storage and document metadata storage are independent roles. Either role can be configured alone, and each can use a different backend. Caller-supplied synchronous mappers produce complete storage documents, including identifiers and schema-specific field names.

#### Markdown Storage Contract

[src/ingestra/store/markdown/__init__.py](src/ingestra/store/markdown/__init__.py) exports `BaseMarkdownStore`.

[src/ingestra/store/markdown/base.py](src/ingestra/store/markdown/base.py) defines `store_markdown(chunks, chunk_mapper=...)`. It maps embedded chunks to storage dictionaries before delegating writes to the provider's asynchronous `_store_documents()` implementation. This keeps chunk mapping separate from backend-specific persistence.

#### Metadata Storage Contract

[src/ingestra/store/metadata/__init__.py](src/ingestra/store/metadata/__init__.py) exports `BaseMetadataStore`.

[src/ingestra/store/metadata/base.py](src/ingestra/store/metadata/base.py) defines `store_metadata(metadata, metadata_mapper=...)`. It maps document-level metadata into a storage document and delegates to `_store_documents()`. Metadata does not have to be stored alongside chunk text or embeddings.

#### Azure AI Search Adapter

[src/ingestra/store/azureaisearch.py](src/ingestra/store/azureaisearch.py) defines `AzureAISearchStore`, which implements both storage roles for one existing search index. It accepts a caller-owned asynchronous `SearchClient` targeting that index and an index schema, discovers the key field, and validates nonempty, unique document keys before upload.

Uploads are grouped into batches of at most 1,000 documents. Every indexing result must succeed, and returned keys must match the uploaded batch. The adapter does not create indexes or choose field names. Separate instances and document clients can target different indexes for chunks and metadata. It uses the supplied client directly without changing its configuration or closing it.

#### Azure SQL Adapter and Vector Type

[src/ingestra/store/azuresql.py](src/ingestra/store/azuresql.py) provides `AzureSQLStore` and `AzureSQLVector`.

`AzureSQLStore` implements both roles against one existing SQLAlchemy table. It requires a SQL Server asynchronous connection, a primary key, and an active caller-owned transaction. It validates mapped column names and primary keys, then inserts or updates rows using bound parameters. Its existence checks use SQL Server update and serializable-range locks. It never creates tables, commits, or closes the connection.

`AzureSQLVector` is a SQLAlchemy type for native `VECTOR(dimensions)` columns. It validates dimensions from 1 through 1,998 and finite numeric vector elements, serializes bound values as JSON for server-side casts, and decodes selected vectors from their text representation. Private encoder and decoder protocols describe the processor call signatures.

## Samples

### Contract Ingestion

#### Application Entry Point

[samples/contract-ingestion/function_app.py](samples/contract-ingestion/function_app.py) registers two Azure Functions using the Python decorator programming model. `IngestHttp` accepts a raw-body `POST /api/ingest` upload with a filename query parameter and function-level authentication. It returns JSON with ingestion results or validation and provider error responses. `IngestBlob` processes uploads through an Event Grid-backed blob trigger and propagates failures for host retry handling. Blob reads are bounded by the sample upload limit.

#### Application Service

[samples/contract-ingestion/services/__init__.py](samples/contract-ingestion/services/__init__.py) marks the sample's service package.

[samples/contract-ingestion/services/ingestion.py](samples/contract-ingestion/services/ingestion.py) owns the sample ingestion workflow. `validate_file()` rejects empty bodies, invalid filenames, and uploads larger than 20 MiB. `ingest_file()` derives a stable document ID from the source identity and creates ordered chunk IDs, provenance fields, and storage mappers.

The service creates and closes Azure clients, acquires an Entra token for SQL, and configures the pipeline with a 2,048-token chunk-size goal and 1,536-dimensional embeddings. It calls `convert` and `chunk`, then `ingest_metadata` and `ingest_chunks`. Separate `AzureSQLStore` instances write document metadata and chunks through the same transaction. Empty extraction raises `EmptyExtractionError` to roll back writes. Successful reingestion deletes obsolete trailing chunks before commit, so a shorter replacement does not leave stale rows.

#### Database and Bootstrap Utilities

[samples/contract-ingestion/utilities/__init__.py](samples/contract-ingestion/utilities/__init__.py) marks the sample's utility package.

[samples/contract-ingestion/utilities/database.py](samples/contract-ingestion/utilities/database.py) defines shared SQLAlchemy metadata and two tables: `dbo.document_metadata` for document identity, provenance, and extracted fields; and `dbo.document_chunks` for ordered text, page numbers, and native vectors. A foreign key links chunks to their document. `create_sql_engine()` builds an encrypted `mssql+aioodbc` connection using Microsoft ODBC Driver 18, a binary-packed Entra access token, and `NullPool`. The caller owns engine disposal.

[samples/contract-ingestion/utilities/bootstrap.py](samples/contract-ingestion/utilities/bootstrap.py) provides a command-line initialization step. It uses `AzureCliCredential` to create the SQL tables and create or validate the Function identity's SQL user. It grants table-level `SELECT`, `INSERT`, `UPDATE`, and `DELETE` permissions. It does not configure AI services, model defaults, or analyzers.

#### Host Configuration and Deployment

* [samples/contract-ingestion/host.json](samples/contract-ingestion/host.json) contains Azure Functions host configuration.
* [samples/contract-ingestion/local.settings.json.example](samples/contract-ingestion/local.settings.json.example) provides a local application settings template rather than checked-in secrets.
* [samples/contract-ingestion/.funcignore](samples/contract-ingestion/.funcignore) excludes development files from Function publishing.
* [samples/contract-ingestion/Deploy-Sample.ps1](samples/contract-ingestion/Deploy-Sample.ps1) coordinates dependency preparation, wheel and ZIP packaging, infrastructure deployment, data-plane bootstrap, Function publishing, and event wiring.
* [samples/contract-ingestion/infra/main.bicep](samples/contract-ingestion/infra/main.bicep) declares the Function application and hosting plan, managed identity, Storage, Azure SQL, and storage role assignments. It invokes modules for runtime access to an existing Foundry account and workspace-based monitoring; it does not provision AI accounts or model deployments.
* [samples/contract-ingestion/infra/foundry-access.bicep](samples/contract-ingestion/infra/foundry-access.bicep) grants the Function identity account-scoped Content Understanding Reader and OpenAI User roles on the existing Foundry account.
* [samples/contract-ingestion/infra/monitoring.bicep](samples/contract-ingestion/infra/monitoring.bicep) creates a Log Analytics workspace with 30-day retention and workspace-based Application Insights, supplying the Function's monitoring connection string.
* [samples/contract-ingestion/infra/events.bicep](samples/contract-ingestion/infra/events.bicep) creates the Storage Event Grid system topic and event subscription used for blob-trigger delivery after the application is published.
* [samples/contract-ingestion/README.md](samples/contract-ingestion/README.md) contains deployment prerequisites, settings, invocation examples, local development steps, and operational limitations.

Install the sample dependency group with `uv sync --group samples` from the repository root.
