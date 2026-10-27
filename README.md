---
title: Ingestra
description: Composable document ingestion for search and retrieval-augmented generation.
---

## Ingestra

Document ingestion for Python. Convert, chunk, embed, and store.

[![Python 3.12+](https://img.shields.io/badge/python-3.12%2B-blue.svg)](https://www.python.org/downloads/)

[Installation](#installation) |
[Quick start](#quick-start) |
[Documentation](#documentation) |
[Contributing](#contributing)

Ingestra turns documents into Markdown chunks, embeddings, and metadata for
search and retrieval-augmented generation (RAG). Compose a pipeline from
interchangeable components, or use each component on its own.

```text
Document -> Markdown -> Chunks -> Embeddings -> Storage
```

## Features

- Recursive Markdown chunking near a configurable token size, with structural context
- Lossless source text and page attribution when page markers are available
- Async document conversion, embedding generation, and storage
- Independent storage backends for embedded chunks and document metadata
- Public interfaces for bringing your own converters, chunkers, and providers

## Installation

Requires Python 3.12 or newer. Install from Git in an existing
[uv](https://docs.astral.sh/uv/getting-started/installation/)-managed project:

```powershell
uv add "ingestra @ git+https://github.com/krprashantpk/ingestra.git"
```

Git must be installed. You can pin the dependency by appending
`@<tag-or-commit>` to the URL.

## Quick start

Already have Markdown? Split it near a token-size goal without an Azure
account:

```python
"""Split Markdown into chunks for embedding."""

from ingestra.chunker import MarkdownTokenChunker

chunker = MarkdownTokenChunker(chunk_size=2048)
chunks = chunker.chunk("# Getting started\n\nIngestra prepares documents for retrieval.")

for chunk in chunks:
    print(chunk.embedding_text)
    print(chunk.token_count)
```

Each chunk includes its original text, embedding-ready text, token count, and
source page numbers when available. The token size is a soft goal, not a hard
ceiling; natural boundaries and structural context can take chunks above it.
The default `tiktoken` tokenizer may download its encoding data on first use.

### Build an ingestion pipeline

Inside your async application, pass a configured converter and embedding
provider to `Pipeline`:

```python
from ingestra.chunker import MarkdownTokenChunker
from ingestra.pipeline import Pipeline

pipeline = Pipeline(converter, MarkdownTokenChunker(), embeddings)
markdown, metadata = await pipeline.convert(document_bytes)
chunks = await pipeline.chunk(markdown)
```

`chunks` contains the source text, embedding input, vector, and page numbers for
each chunk. `metadata` contains document-level metadata.
`convert()` returns Markdown and metadata; `chunk()` chunks and embeds Markdown
without invoking the converter. You can also pass existing Markdown directly to
`chunk()`. Neither method writes to storage. With configured stores, call
`ingest_chunks(chunks, chunk_mapper=...)` or
`ingest_metadata(metadata, metadata_mapper=...)` to persist either output
independently. Compose these processing and persistence calls explicitly in
your application for end-to-end ingestion.

See the [complete Azure example](docs/guide.md#convert-and-embed-a-document)
for client setup and authentication, and the
[storage examples](docs/guide.md#stores) for persistence.

## Integrations

| Stage                | Built-in implementation                                                                   |
|----------------------|-------------------------------------------------------------------------------------------|
| Document conversion  | [Azure Content Understanding](docs/guide.md#azure-content-understanding)                  |
| Markdown chunking    | [MarkdownTokenChunker](docs/guide.md#markdown-token-chunking)                             |
| Embedding generation | [Azure OpenAI](docs/guide.md#azure-openai)                                                |
| Storage              | [Azure AI Search](docs/guide.md#azure-ai-search) and [Azure SQL](docs/guide.md#azure-sql) |

Azure integrations require provisioned services and appropriate permissions.
Search indexes and SQL tables must already exist. Azure SQL also requires
[Microsoft ODBC Driver 18](https://learn.microsoft.com/en-us/sql/connect/odbc/download-odbc-driver-for-sql-server)
on the host.

## Extending Ingestra

Subclass the interface for the component you want to replace:

- `BaseConverter`: implement async `convert()` to return Markdown and metadata
- `BaseChunker`: implement `chunk()` to return ordered `Chunk` objects
- `BaseEmbeddings`: implement async `generate()` to return one vector per input
- `BaseMarkdownStore` or `BaseMetadataStore`: implement async
  `_store_documents()` to persist mapped records

Pass your implementation to the pipeline alongside the other components.
No plugin registration or changes to the pipeline are needed.

The [extension guide](docs/guide.md#extending-ingestra) includes a custom
converter example and the contracts each implementation must preserve.

## Documentation

- [User guide and component reference](docs/guide.md)
- [Interactive Markdown chunking notebook](exeperiment/chunkers/markdown_chunking.ipynb)
  with 12 samples larger than 4096 tokens, one adjustable token-size goal,
  and side-by-side source/embedding comparisons
- [Architecture and design](architecture.md)
- [Local development and testing](docs/guide.md#local-development-setup)
- [Azure Functions example](samples/contract-ingestion/README.md), including
  HTTP and Blob ingestion into Azure SQL

## Local development

Clone the repository and install it in editable mode:

```powershell
git clone https://github.com/krprashantpk/ingestra.git
Set-Location .\ingestra
uv sync
```

Run tests and build the package from the repository root:

```powershell
uv run python -m unittest discover -s tests -v
uv build
```

Use the root `.venv` for development. Most tests mock external services and
need no Azure credentials. See the [testing notes](docs/guide.md#tests) for
the document-fixture prerequisite and the
[sample development instructions](docs/guide.md#develop-the-functions-sample)
for the optional Functions dependencies.

## Contributing

Bug reports, documentation improvements, examples, and new integrations are
welcome. [Open an issue](https://github.com/krprashantpk/ingestra/issues) to
report a bug or discuss a larger change before starting work.

Include tests for behavior changes and follow the
[repository coding conventions](AGENTS.md) when submitting a pull request.
