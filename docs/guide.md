---
title: Ingestra guide
description: Configuration, examples, component contracts, storage, and local development for Ingestra.
---

[Back to the README](../README.md)

## What is Ingestra

Ingestra is a Python library that prepares documents for search,
retrieval-augmented generation (RAG), and other document-processing applications.
It turns raw document bytes into Markdown, splits that Markdown into
token-budgeted chunks, generates embeddings, and optionally persists the
chunks and document metadata.

```text
Document bytes --> Converter --> Markdown + metadata
                                     |
                                  Chunker
                                     |
                             Embedding provider
                                     |
                                ChunkResult
                                     |
                    Optional chunk and metadata stores
```

You choose and configure each component. Use the complete pipeline or call a
converter, chunker, embedding provider, or store independently.

- Convert documents with Azure Content Understanding.
- Split Markdown locally while retaining source text, heading context, and
  page attribution when available.
- Generate vectors with an Azure OpenAI embedding deployment.
- Store embedded chunks and metadata independently in Azure AI Search, Azure
  SQL, or a combination of the two.
- Replace individual components through public abstract interfaces without
  changing the pipeline.

Ingestra is a library, not a hosted ingestion service, crawler, search API, or
chat application. Your application owns document loading, client credentials,
resource provisioning, retries, and client lifetimes.

### Getting started

- [Install Ingestra](#installation) in an application.
- [Try the local quick start](#chunk-markdown-without-azure) or
  [process a document end to end](#convert-and-embed-a-document).
- [Extend Ingestra](#extending-ingestra) with your own components.
- [Set up local development](#local-development-setup) to work on this repository.
- [Run the Azure Functions sample](#azure-functions-sample) for HTTP and Blob ingestion.
- Browse the [project structure](#project-structure) and
  [architecture](../architecture.md).

Component details: [converters](#converters), [chunkers](#chunkers),
[embeddings](#embeddings), [pipeline](#pipeline), and [stores](#stores).

## Requirements

- Python 3.12 or newer
- [uv](https://docs.astral.sh/uv/getting-started/installation/) for the
  installation and development commands below
- Git when installing from the repository

Local Markdown chunking and mocked unit tests do not require an Azure account.
The built-in Azure adapters require provisioned services and an identity with
the appropriate access. Azure SQL additionally requires
[Microsoft ODBC Driver 18 for SQL Server](https://learn.microsoft.com/en-us/sql/connect/odbc/download-odbc-driver-for-sql-server)
on the host; native vector columns require a compatible SQL deployment.

## Installation

To add the current repository version to an existing uv-managed application,
run this command from that application's project directory:

```powershell
uv add "ingestra @ git+https://github.com/krprashantpk/ingestra.git"
```

This installs from source without assuming a published package is available.
For a reproducible source dependency, append `@<tag-or-commit>` to the Git URL.
The distribution name and Python import name are both `ingestra`.

Verify the installation:

```powershell
uv run python -c "import ingestra; print(ingestra.__version__)"
```

The declared dependencies include the Azure SDKs, OpenAI SDK, SQLAlchemy,
`aioodbc`, and `tiktoken`; no separate provider extras are defined. To edit the
library itself, follow [local development setup](#local-development-setup)
instead.

## Usage

### Chunk Markdown without Azure

If you already have Markdown, use the chunker directly. Save this example as
`quickstart.py` in your application or repository root:

```python
"""Split Markdown locally and verify that the source is preserved."""

from ingestra.chunker import MarkdownTokenChunker

markdown = (
    "# Service agreement\n\n"
    "Payment is due within 30 days of receiving an invoice.\n\n"
    "## Renewal\n\n"
    "The agreement renews annually unless either party gives notice."
)
chunker = MarkdownTokenChunker(chunk_size=2048)
chunks = chunker.chunk(markdown)

assert "".join(chunk.original_text for chunk in chunks) == markdown
assert all(chunk.embedding_text and chunk.token_count is not None for chunk in chunks)
print("Chunks:", len(chunks))
for chunk in chunks:
    print(chunk.token_count, chunk.embedding_text)
```

Run it with:

```powershell
uv run python .\quickstart.py
```

Each chunk contains the original source slice plus embedding-ready text and its
token count. This example does not convert binary documents, generate vectors,
or write to storage. The default tokenizer may download its public encoding
data on first use; subsequent runs can use the cached data.

### Convert and embed a document

To process a PDF or another format supported by your analyzer, configure an
Azure Content Understanding resource and an Azure OpenAI embedding deployment.
The Content Understanding analyzer's required model configuration must also be
ready. Installation alone does not provision these resources.

The following example uses Azure Identity. Install the
[Azure CLI](https://learn.microsoft.com/en-us/cli/azure/install-azure-cli)
and sign in for local use. Your identity needs permission to analyze documents
and the `Cognitive Services OpenAI User` role on the Azure OpenAI resource.
Set these values in the same PowerShell session that runs the script:

```powershell
az login
$env:AZURE_CONTENT_UNDERSTANDING_ENDPOINT = "https://<your-content-understanding-endpoint>"
$env:AZURE_CONTENT_UNDERSTANDING_ANALYZER = "prebuilt-documentSearch"
$env:AZURE_OPENAI_ENDPOINT = "https://<your-openai-resource>.openai.azure.com"
$env:AZURE_OPENAI_EMBEDDING_DEPLOYMENT = "<your-embedding-deployment-name>"
```

Save this as `ingest_document.py`:

```python
"""Convert a document to Markdown chunks and generate embeddings without storage."""

import asyncio
import os
import sys
from pathlib import Path

from azure.ai.contentunderstanding.aio import ContentUnderstandingClient
from azure.identity.aio import DefaultAzureCredential, get_bearer_token_provider
from openai import AsyncAzureOpenAI

from ingestra.chunker import MarkdownTokenChunker
from ingestra.converter import AzureContentUnderstandingConverter
from ingestra.embeddings import AzureOpenAIEmbeddings
from ingestra.pipeline import Pipeline


async def main() -> None:
    """Process the document supplied as the first command-line argument."""
    data = Path(sys.argv[1]).read_bytes()
    async with DefaultAzureCredential() as credential:
        token_provider = get_bearer_token_provider(credential, "https://cognitiveservices.azure.com/.default")
        async with ContentUnderstandingClient(endpoint=os.environ["AZURE_CONTENT_UNDERSTANDING_ENDPOINT"], credential=credential) as cu_client:
            async with AsyncAzureOpenAI(azure_endpoint=os.environ["AZURE_OPENAI_ENDPOINT"], api_version="2024-10-21", azure_ad_token_provider=token_provider) as openai_client:
                converter = AzureContentUnderstandingConverter(cu_client, analyzer_id=os.environ["AZURE_CONTENT_UNDERSTANDING_ANALYZER"])
                embeddings = AzureOpenAIEmbeddings(openai_client, deployment_name=os.environ["AZURE_OPENAI_EMBEDDING_DEPLOYMENT"])
                pipeline = Pipeline(converter=converter, chunker=MarkdownTokenChunker(), embeddings=embeddings)
                markdown, metadata = await pipeline.convert(data)
                chunks = await pipeline.chunk(markdown)
                print("Metadata:", metadata)
                print("Embedded chunks:", len(chunks))
                for chunk in chunks:
                    print(chunk.page_numbers, len(chunk.embedding), chunk.original_text)


asyncio.run(main())
```

Pass the path to an existing document:

```powershell
uv run python .\ingest_document.py .\example.pdf
```

This makes billable Azure requests. Conversion returns document-level metadata
alongside Markdown, and chunking returns ordered chunks with their original text, exact embedding input, vector, and
source page numbers. No storage writes occur. The built-in converter retains
only the first content item returned by the analyzer.

To persist the result, configure one or both [stores](#stores), supply the
corresponding mapping callbacks, and call `await pipeline.ingest(...)` instead
of the separate conversion and chunking calls. Indexes and tables must already exist, vector
dimensions must match the embedding model, and SQL writes need a caller-owned
transaction. See [ingest and store](#ingest-and-store) for the write contract
and [the Functions sample](../samples/contract-ingestion/README.md) for a complete
application.

## Converters

[`BaseConverter`](../src/ingestra/converter/base.py) is the abstract interface for
asynchronous conversion of raw bytes to Markdown text and metadata:

```python
from ingestra.converter import BaseConverter


async def convert_document(
    data: bytes, converter: BaseConverter
) -> tuple[str, dict[str, object]]:
    markdown, metadata = await converter.convert(data)
    return markdown, metadata
```

To add a converter, subclass `BaseConverter` and implement async `convert(data)`.
Return a two-item tuple containing the Markdown string first and a metadata
dictionary second. Metadata keys are strings and values may be any Python
object; use `{}` when no metadata is available. Non-bytes inputs must raise
`TypeError`, and unsupported formats and conversion errors must raise explicitly.
Supported formats, configuration, and resource ownership remain
implementation-specific. The base class and subclasses without `convert()`
cannot be instantiated.

### Azure Content Understanding

[`AzureContentUnderstandingConverter`](../src/ingestra/converter/azurecontentunderstanding.py)
implements `BaseConverter` using a caller-owned async Azure SDK client.
Configure the analyzer once in the constructor, then call `convert(data)` with
raw bytes:

```python
import asyncio
import os

from azure.ai.contentunderstanding.aio import ContentUnderstandingClient
from azure.identity.aio import DefaultAzureCredential

from ingestra.converter import AzureContentUnderstandingConverter


async def main() -> None:
    async with DefaultAzureCredential() as credential:
        async with ContentUnderstandingClient(
            endpoint=os.environ["AZURE_CONTENT_UNDERSTANDING_ENDPOINT"],
            credential=credential,
        ) as client:
            converter = AzureContentUnderstandingConverter(
                client, analyzer_id="prebuilt-documentSearch"
            )
            with open("example.pdf", "rb") as stream:
                markdown, metadata = await converter.convert(stream.read())
            print(markdown)
            print(metadata)


asyncio.run(main())
```

- Markdown and flattened field metadata come from the **first content item
  only**. Nested objects and arrays retain their structure; dates and datetimes
  become ISO strings.
- Markdown is formatted with the Azure SDK's `to_llm_input` helper, adding YAML
  front matter and `InputPageNumber` comments for chunk page attribution.
  Extracted fields are returned separately as metadata and are not duplicated
  in the formatted Markdown (`include_fields=False`).
- Missing contents return `("", {})` with a warning. Missing, empty, or whitespace-only
  Markdown on the first content item returns an empty string with a warning while retaining
  that item's fields; later content items are never used as a fallback.
- Non-bytes input raises `TypeError`. A non-string or blank `analyzer_id` raises
  `TypeError` or `ValueError`, respectively. SDK, polling, and formatting errors propagate.
- Authentication, retries, timeouts, and cleanup belong to the supplied async
  client. Supported formats and limits depend on the configured Azure analyzer.

This replaces `AzureContentUnderstandingClient.analyze(data, analyzer_id)`;
import `AzureContentUnderstandingConverter` from `ingestra.converter`, supply
`analyzer_id` at construction, and unpack `await converter.convert(data)`
instead of accessing `AnalyzeFileResult.markdown` and `.fields`.

## Chunkers

[`BaseChunker`](../src/ingestra/chunker/base.py) is the abstract interface for
synchronous text chunking. Application code can depend on the interface while
the caller selects and configures the implementation. Every strategy returns
`list[Chunk]`, using the same immutable
[`Chunk`](../src/ingestra/chunker/base.py) model for downstream processing:

```python
from ingestra.chunker import BaseChunker, Chunk, MarkdownTokenChunker


def split_document(text: str, chunker: BaseChunker) -> list[Chunk]:
    return chunker.chunk(text)


chunker = MarkdownTokenChunker(chunk_size=2048)
chunks = split_document("# Heading\n\nDocument text.", chunker)
```

To add another strategy, subclass `BaseChunker` and implement `chunk(text)`,
returning `list[Chunk]`. Always return a list in **source order**, never sorted
by content or page number, and `[]` for empty or whitespace-only input;
non-string input must raise `TypeError`. Pass the source text
positionally through the interface, allowing implementations to retain their
format-specific parameter names. Constructors, chunk boundaries, overlap, and
size limits remain implementation-specific.

`Chunk` has exactly four fields:

- `original_text: str`: the original source slice, replacing the previous `text` field.
- `embedding_text: str | None`: optional embedding-ready input with context.
- `token_count: int | None`: the token count of that embedding input.
- `page_numbers: tuple[int, ...]`: source page numbers when available.

`MarkdownTokenChunker` populates embedding text, its token count, and source
pages when available. Headings and structural bookkeeping remain internal
to the chunker rather than appearing in its result model.
Embedding generators still accept sequences of strings, not chunk objects.

### Markdown token chunking

[`MarkdownTokenChunker`](../src/ingestra/chunker/markdown.py) packs Markdown
locally near **`chunk_size=2048` tokens** by default. This is the only sizing
parameter. It is a soft token goal, not a character count or hard ceiling.
No Azure conversion or embedding requests are made by the chunker.

A short document becomes one chunk. Larger documents are filled across heading
sections and blocks rather than emitting a short chunk for each section.
Around the token goal, the chunker chooses the nearest complete sentence, code
line, or table row. It can go slightly above the goal when that boundary is
closer than an early cut, or when repeated structural context requires room.
The final remainder can be smaller. An individually oversized sentence, row, or
line is recursively split at finer row, cell, line, word, and character
boundaries; an entire large section is not exempted from splitting.

**Where to start reading the implementation:** begin with
[`MarkdownTokenChunker.chunk`](../src/ingestra/chunker/markdown.py), then follow
the short `_TokenChunker.chunk` workflow in
[`_token.py`](../src/ingestra/chunker/_token.py). Markdown recognition and
preferred split boundaries are isolated in
[`_structure.py`](../src/ingestra/chunker/_structure.py). See the
[reading guide](../architecture.md#reading-the-markdown-chunker) for the stage order.

The default tokenizer, `tiktoken`, is installed with `ingestra`. To override it,
supply a `tokenizer: Callable[[str], int]`.

```python
from ingestra.chunker import MarkdownTokenChunker

chunker = MarkdownTokenChunker(chunk_size=2048)
markdown = "# Heading\n\nDocument text."
chunks = chunker.chunk(markdown)
embedding_inputs = [chunk.embedding_text for chunk in chunks]
assert "".join(chunk.original_text for chunk in chunks) == markdown
```

For a `list[str]` containing one string per page, the optional static
[`pages_to_markdown`](../src/ingestra/chunker/markdown.py) helper returns a single
string with `<!-- InputPageNumber: N -->` comments, numbered from one:

```python
markdown = MarkdownTokenChunker.pages_to_markdown(["First page.", "Second page."])
```

It preserves each page's content verbatim, including whitespace and empty
pages, and returns `""` for an empty list. Non-list inputs or non-string pages
raise `TypeError`. No page headers or footers are added. The helper does not
chunk text, load a tokenizer, or run automatically in the chunker or pipeline.
Page markers provide attribution, not mandatory chunk boundaries.

The default is a starting point, not a universal retrieval-quality optimum.
Because natural boundaries can exceed the goal, validate actual chunk token
counts against your provider's per-input limit and validate batch limits
separately. The chunker does not expose a provider hard-limit setting.
The default tokenizer is
`cl100k_base`, suitable for OpenAI/Azure OpenAI `text-embedding-3-small` and
`text-embedding-3-large`. Its first use may download public tokenizer data.
`MarkdownTokenChunker` creates this default once per instance and counts the
IDs from `encoding.encode_ordinary(text)` using `len(...)`. The internal
splitting engine receives the resolved callable and does not load tokenizers.
Other models can supply `tokenizer=lambda text: ...` returning their exact,
nonnegative integer token count, not token IDs, including any required special tokens. A
custom tokenizer bypasses `tiktoken` initialization. Automatic tokenizer
truncation must be disabled.

- `chunk_size` defaults to 2048 and must be a positive integer; booleans are
  rejected. Sizes always count tokens. The optional `tokenizer` collaborator
  supports another model's tokenization; it is not a character-mode setting.
- Selection measures the **final `embedding_text`**, including heading context,
  repeated headers, and code fences. It chooses the closest natural boundary,
  preferring the under-goal boundary when two are equally close. Most non-final
  chunks should be near the goal, not substantially underfilled just to preserve
  a section boundary. Natural atomic-unit sizes can still affect that distance.
- Oversized prose is split at sentence boundaries, then spaces, then Python
  character boundaries. Fenced code prefers line boundaries and repeats its
  language/fences. Tables prefer whole rows, repeating explicit HTML `<th>`
  headers or Markdown headers. Headerless HTML tables do not invent column
  names. HTML `rowspan` groups stay together when they fit; original merged-cell
  attributes remain in the source. Pipe tables can follow prose without a blank
  line. Preceding Setext heading underlines are not treated as table separators.
- Individually oversized rows, sentences, lines, metadata, figures, comments,
  and malformed/unclosed blocks are recursively fragmented. Such fragments
  are **not guaranteed to be independently valid Markdown/HTML**. Retrieve
  the original document or adjacent chunks in the returned list when complete
  structure is needed.
- Active Markdown headings, explicit table headers, and code fences can be
  repeated as structural context. Prose overlap is not added. Disproportionately
  large optional headings or headers may be omitted to leave room for content,
  with a warning logged. Original headings and headers remain in `original_text`.
- `original_text` retains exact, non-overlapping source slices. Joining these values
  still reconstructs nonblank input. Embed
  **`embedding_text`**, which includes structural context and may normalize table
  grouping tags, rather than `original_text`. `token_count` describes that final input.
- `page_numbers` tracks CU `InputPageNumber` comments, including markers within
  tables; fenced-code examples of markers, including those nested in lists
  or blockquotes, do not change page attribution.
  Use these page numbers with a document identifier for citations; chunks do
  not expose individual source start/end indices.
  Page markers and YAML metadata remain in the lossless source and are not
  silently discarded. Heading detection follows explicit Markdown headings,
  not guesses about unmarked legal clause numbers or OCR layout.
- Tokenizer/provider errors propagate. Invalid settings raise explicitly. A
  size too small for even one source character raises
  `ValueError`; content is never silently truncated.
- Empty or whitespace-only input returns `[]`; non-string input raises
  `TypeError`. Source whitespace and line endings are preserved exactly.

**Breaking API change:** replace `max_tokens`, `target_tokens`, and
`overlap_tokens` with `MarkdownTokenChunker(chunk_size=2048)`, or omit the size
to use its default. The old sizing keywords are rejected rather than silently
ignored. There is no prose-overlap option. The combined `MarkdownChunker` and
character-mode chunking remain removed; `chunk_size` now always means tokens.
The optional token-count callback is named `tokenizer`.

Real-tokenizer tests use the required `tiktoken` dependency; custom-tokenizer
tests use deterministic counts. The
[Markdown chunker tests](../tests/test_markdown_chunker.py) cover exact source
reconstruction, token budgets, and page attribution without Azure conversion
or embedding requests. See [Tests](#tests) for local fixture requirements.

## Embeddings

[`BaseEmbeddings`](../src/ingestra/embeddings/base.py) is the abstract interface
for asynchronous embedding generation. Application code can depend on this
interface while the caller selects and configures the concrete provider:

```python
from collections.abc import Sequence

from ingestra.embeddings import BaseEmbeddings


async def embed_documents(
    texts: Sequence[str], embeddings: BaseEmbeddings
) -> list[list[float]]:
    return await embeddings.generate(texts)
```

To add another provider, subclass `BaseEmbeddings` and implement async
`generate(texts)`. Return one vector per input in input order, and `[]` for
empty input. Invalid inputs and provider errors must raise explicitly; inputs
must not be silently truncated. Provider-specific configuration, limits, and
resource ownership remain with the concrete implementation. The abstract base
class and subclasses without `generate()` cannot be instantiated.

### Azure OpenAI

[`AzureOpenAIEmbeddings`](../src/ingestra/embeddings/azureopenai.py) generates
embeddings asynchronously using the included OpenAI SDK. Supply an
`AsyncAzureOpenAI` client and your Azure **embedding deployment name**.
The client controls authentication, retries, and timeouts, and remains
caller-owned.

This example uses async Azure Identity authentication. The identity needs the
`Cognitive Services OpenAI User` role on the Azure OpenAI resource.

```python
import asyncio
import os

from azure.identity.aio import DefaultAzureCredential, get_bearer_token_provider
from openai import AsyncAzureOpenAI

from ingestra.embeddings import AzureOpenAIEmbeddings, BaseEmbeddings


async def main() -> None:
    async with DefaultAzureCredential() as credential:
        token_provider = get_bearer_token_provider(
            credential, "https://cognitiveservices.azure.com/.default"
        )
        async with AsyncAzureOpenAI(
            azure_endpoint=os.environ["AZURE_OPENAI_ENDPOINT"],
            api_version="2024-10-21",
            azure_ad_token_provider=token_provider,
        ) as client:
            embeddings: BaseEmbeddings = AzureOpenAIEmbeddings(
                client,
                deployment_name=os.environ["AZURE_OPENAI_EMBEDDING_DEPLOYMENT"],
            )
            vectors = await embeddings.generate(["First document", "Second document"])
            print(vectors)


asyncio.run(main())
```

- `generate(texts)` returns `list[list[float]]`, one vector per text in input
  order, including when the service returns its indexed results out of order.
  Pass a one-item list to embed a single string. An empty list returns `[]`
  without making a request.
- For token-mode Markdown chunks, use
  `await embeddings.generate([chunk.embedding_text for chunk in chunks])`.
- Each call sends **one request**, with at most **2,048** inputs. Split larger
  collections into separate calls. Inputs must be nonblank strings; original
  whitespace is preserved. Invalid inputs raise before any request is made.
- Set `dimensions=` on the generator for models that support reduced
  dimensionality, such as `text-embedding-3-small` and `text-embedding-3-large`.
  Otherwise the model's default dimensionality is used.
- Token limits are not checked by this component and inputs are never
  truncated. Respect your deployment's per-input limit and the service's
  **300,000-token aggregate limit per request**, in addition to rate limits.
  Token-safe chunking alone does not validate the aggregate batch limit.
- SDK errors propagate unchanged. Missing, duplicate, or out-of-range response
  indices raise `RuntimeError` rather than misaligning vectors and source texts.
  Close the supplied SDK client using its async context manager or
  `await client.close()`.

## Pipeline

[`Pipeline`](../src/ingestra/pipeline.py) composes a configured converter, chunker,
embedding provider, and optional independent Markdown and metadata stores.
Its async `convert(data)` method accepts raw bytes and returns
`(markdown, metadata)`. Its async `chunk(markdown)` method
chunks Markdown synchronously and generates embeddings asynchronously without
invoking the converter:

```python
from ingestra.chunker import MarkdownTokenChunker
from ingestra.converter import BaseConverter
from ingestra.embeddings import BaseEmbeddings
from ingestra.pipeline import EmbeddedChunk, Pipeline


async def chunk_document(data: bytes, converter: BaseConverter, embeddings: BaseEmbeddings) -> list[EmbeddedChunk]:
  pipeline = Pipeline(converter=converter, chunker=MarkdownTokenChunker(), embeddings=embeddings)
    markdown, _ = await pipeline.convert(data)
    return await pipeline.chunk(markdown)
```

For existing Markdown, call `await pipeline.chunk(markdown)` directly. Keep the
metadata returned by `convert` separately when needed.

The returned `list[EmbeddedChunk]` contains records in source order, each with
`original_text: str`, `embedding_text: str`, `embedding: list[float]`, and
`page_numbers: tuple[int, ...] = ()`. The shared models are defined in
[types.py](../src/ingestra/types.py).

The pipeline embeds the chunker's `embedding_text` when it is not `None`;
otherwise it uses `original_text`. The result's `embedding_text` always records
the exact text sent to the embedding provider. The existing shared `Chunk`
model remains unchanged. `EmbeddedChunk` stays separate from `Chunk` so its
embedding text and vector remain required. The default empty page tuple keeps
existing three-argument construction supported.

The pipeline preserves the chunker's `page_numbers`, including chunks that span
multiple pages. Unknown pages remain `()`. Storage callbacks receive the same page
tuples; include `list(chunk.page_numbers)` in a mapper when the target schema
supports page citations. Stores do not add page fields automatically.

Empty chunk lists return `[]` without
calling the embedding provider. `convert` rejects non-bytes input; `chunk`
rejects non-string Markdown.
These invalid inputs raise `TypeError` before processing. Component errors
propagate unchanged, and a missing or extra embedding raises
`RuntimeError` rather than silently misaligning results.

The pipeline calls `generate()` once for all nonempty chunks; it does not batch,
truncate, retry, or enforce provider-specific limits. Configure token-safe
chunking when needed and respect the embedding provider's input-count and
aggregate token limits. Supplied components and SDK clients remain caller-owned.

### Ingest and store

Configure `markdown_store=`, `metadata_store=`, or both on the pipeline. Persist
already-prepared chunks and metadata independently:

```python
await pipeline.ingest_chunks(chunks, chunk_mapper=map_chunk)
await pipeline.ingest_metadata(metadata, metadata_mapper=map_metadata)
```

Each method returns `None`, requires only its matching store and mapper, and
does not convert, chunk, or embed data. A missing matching store raises
`ValueError`; a non-callable mapper raises `TypeError` before storage. Store and
mapper errors propagate unchanged. Empty chunk sequences perform no provider
writes; empty metadata still produces a mapped document. Calling these methods
separately leaves write ordering to the caller.

Use `ingest(data, *, chunk_mapper=None, metadata_mapper=None)` to process and
persist in one operation. With caller-configured components, stores, and mapping callbacks:

```python
pipeline = Pipeline(converter, MarkdownTokenChunker(), embeddings, markdown_store=markdown_store, metadata_store=metadata_store)
result = await pipeline.ingest(data, chunk_mapper=map_chunk, metadata_mapper=map_metadata)
```

- `convert(data)` and `chunk(markdown)` remain **side-effect-free with respect to storage**,
  even when stores are configured. Neither method needs storage mappers.
- `ingest` requires at least one configured store. Only the mapper for each
  configured role is required; omit both the store and mapper for an unused role.
  No stores or a mapper without a matching store raises `ValueError`. Missing or
  non-callable required mappers raise `TypeError`, before conversion or writes.
- Ingestion completes conversion, chunking, and embedding before any writes,
  then awaits `ingest_metadata` followed by `ingest_chunks`. Empty chunk lists
  skip both embedding and Markdown storage but still store configured metadata.
- The returned `ChunkResult` combines the embedded chunk list with conversion
  metadata, not mapped storage dictionaries. Mappers are supplied per call, so each document
  can capture its own identifiers and source-position counter.
- Component, mapper, and storage errors propagate unchanged. A metadata failure
  prevents the Markdown write; a later Markdown failure can leave metadata
  already written. Ingestion does not add retries, compensation, or transactions
  across providers. It never commits SQL transactions or closes caller-owned clients.

Shared result models now live in [types.py](../src/ingestra/types.py) to keep storage
contracts independent of pipeline orchestration. Existing imports of
`ChunkResult` and `EmbeddedChunk` from `ingestra.pipeline` remain supported.

## Stores

Storage has two independent asynchronous contracts:

- [`BaseMarkdownStore`](../src/ingestra/store/markdown/base.py) defines
  `store_markdown(chunks, *, chunk_mapper) -> None` for a sequence of
  `EmbeddedChunk` values, including their Markdown, embedding text, vectors, and
  source page numbers.
- [`BaseMetadataStore`](../src/ingestra/store/metadata/base.py) defines
  `store_metadata(metadata, *, metadata_mapper) -> None` for document metadata.

Both providers implement both contracts. **Each instance targets one index or
table**, so select the provider for each responsibility independently:

| Markdown chunks and embeddings | Document metadata |
|--------------------------------|-------------------|
| Azure AI Search                | Azure SQL         |
| Azure SQL                      | Azure AI Search   |
| Azure AI Search                | Azure AI Search   |
| Azure SQL                      | Azure SQL         |

Use the pipeline's `ingest` operation to invoke configured stores. For example,
this helper captures stable document identifiers and a fresh position counter
for each ingestion call:

```python
from itertools import count

from ingestra.pipeline import ChunkResult, EmbeddedChunk, Pipeline


async def ingest_document(data: bytes, document_id: str, pipeline: Pipeline) -> ChunkResult:
    """Process and persist a document through its configured pipeline."""
    positions = count()

    def map_chunk(chunk: EmbeddedChunk) -> dict[str, object]:
        """Supply the chunk key, linking field, position, text, and vector."""
        position = next(positions)
        return {
            "id": f"{document_id}-{position}",
            "document_id": document_id,
            "chunk_index": position,
            "original_text": chunk.original_text,
            "embedding_text": chunk.embedding_text,
            "embedding": chunk.embedding,
        }

    def map_metadata(metadata: dict[str, object]) -> dict[str, object]:
        """Select document metadata and supply its stable key."""
        return {
            "document_id": document_id,
            "customer_id": metadata.get("customer_id"),
            "title": metadata.get("title"),
        }

    return await pipeline.ingest(data, chunk_mapper=map_chunk, metadata_mapper=map_metadata)
```

The helper above expects both roles to be configured. To use a single role,
provide only its mapper to `ingest`. Stores can also be called directly with
`ChunkResult.chunks` and `ChunkResult.metadata` when separate persistence is needed.

Mappers are required synchronous callbacks returning complete dictionaries,
including keys. There are **no fixed field names**: the fields above are examples.
Each call maps and deep-copies all its documents before performing writes.
Mapping errors propagate before that call writes anything; this guarantee does
not span the two separate calls. Empty chunk sequences perform no writes, while
metadata can still be stored, including metadata mapped from `{}`.

### Azure AI Search

[`AzureAISearchStore`](../src/ingestra/store/azureaisearch.py) accepts a caller-owned
async `SearchClient` and **one complete `SearchIndex` definition**. The client
must target the existing index described by the supplied schema. The store never looks up,
creates, updates, or deletes indexes.

For example, define separate metadata and chunk indexes:

```python
from azure.search.documents.indexes.models import (
    HnswAlgorithmConfiguration,
    SearchableField,
    SearchField,
    SearchFieldDataType,
    SearchIndex,
    SimpleField,
    VectorSearch,
    VectorSearchProfile,
)

from ingestra.store import AzureAISearchStore


metadata_index = SearchIndex(
    name="document-metadata",
    fields=[
        SimpleField(name="document_id", type=SearchFieldDataType.String, key=True),
        SimpleField(
            name="customer_id", type=SearchFieldDataType.String, filterable=True
        ),
        SearchableField(name="title", type=SearchFieldDataType.String),
    ],
)
chunk_index = SearchIndex(
    name="document-chunks",
    fields=[
        SimpleField(name="id", type=SearchFieldDataType.String, key=True),
        SimpleField(
            name="document_id", type=SearchFieldDataType.String, filterable=True
        ),
        SimpleField(
            name="chunk_index", type=SearchFieldDataType.Int32, sortable=True
        ),
        SearchableField(name="original_text", type=SearchFieldDataType.String),
        SearchableField(name="embedding_text", type=SearchFieldDataType.String),
        SearchField(
            name="embedding",
            type=SearchFieldDataType.Collection(SearchFieldDataType.Single),
            searchable=True,
            vector_search_dimensions=1536,
            vector_search_profile_name="chunk-vector-profile",
        ),
    ],
    vector_search=VectorSearch(
        algorithms=[HnswAlgorithmConfiguration(name="chunk-hnsw")],
        profiles=[
            VectorSearchProfile(
                name="chunk-vector-profile",
                algorithm_configuration_name="chunk-hnsw",
            )
        ],
    ),
)
```

Create a caller-owned asynchronous document client for each target index. With
your Search endpoint and credential:

```python
from azure.search.documents.aio import SearchClient


async with (
    SearchClient(endpoint, chunk_index.name, credential) as chunk_search_client,
    SearchClient(endpoint, metadata_index.name, credential) as metadata_search_client,
):
    markdown_store = AzureAISearchStore(chunk_search_client, chunk_index)
    metadata_store = AzureAISearchStore(metadata_search_client, metadata_index)
    pipeline = Pipeline(converter, chunker, embeddings, markdown_store=markdown_store, metadata_store=metadata_store)
    result = await ingest_document(data, "document-1", pipeline)
```

- `SearchIndexClient` is no longer accepted by the store. Pass a configured
  `SearchClient` instead, with your transport, policies, retries, and timeouts
  set on that client. The store uploads through it directly rather than deriving
  a new client with SDK defaults. The caller must close it after all operations.
- The store discovers the schema's key field and rejects schemas without one.
  Mapped keys must be nonempty strings and unique within a write operation.
  Other schema, field, and vector validation belongs to the caller and service.
- Azure AI Search keys must be 1-1,024 letters, digits, `_`, `-`, or `=`, without
  a leading `_`. Supply stable keys for retries. Uploads replace matching
  documents but do not remove obsolete chunks after a shorter re-ingestion.
- Uploads are batched at **1,000 documents**. Other service limits, including
  request byte size, still apply. Failed, missing, duplicate, or unexpected
  indexing results raise `RuntimeError`; SDK exceptions propagate.
- Instances may share a service or even an index. When sharing an index, both
  document shapes must fit its schema and use disjoint keys. Sharing an index
  is not the same as embedding metadata into every chunk.
- Writes across calls and batches are not transactional. The store never enters
  or closes the caller's document client or credential.
  Azure AI Search does not perform cross-index joins.

### Azure SQL

[`AzureSQLStore`](../src/ingestra/store/azuresql.py) accepts a caller-owned SQLAlchemy
`AsyncConnection` and **one `Table` definition** matching an existing table.
SQLAlchemy async support and `aioodbc` are installed with the package. Also install
[Microsoft ODBC Driver 18 for SQL Server](https://learn.microsoft.com/en-us/sql/connect/odbc/download-odbc-driver-for-sql-server)
on the host and configure an `mssql+aioodbc` connection URL.

Example tables compatible with the mappers above:

```python
from sqlalchemy import Column, Integer, MetaData, String, Table, UnicodeText

from ingestra.store import AzureSQLStore, AzureSQLVector


sql_schema = MetaData()
metadata_table = Table(
    "document_metadata",
    sql_schema,
    Column("document_id", String(128), primary_key=True),
    Column("customer_id", String(128)),
    Column("title", UnicodeText),
)
chunk_table = Table(
    "document_chunks",
    sql_schema,
    Column("id", String(256), primary_key=True),
    Column("document_id", String(128), nullable=False),
    Column("chunk_index", Integer, nullable=False),
    Column("original_text", UnicodeText, nullable=False),
    Column("embedding_text", UnicodeText, nullable=False),
    Column("embedding", AzureSQLVector(1536), nullable=False),
)
```

`AzureSQLVector(dimensions)` represents a native float32 `VECTOR(dimensions)`
column. It validates finite numeric lists and their lengths, serializes them to
JSON for ODBC parameter transport, and explicitly casts bound parameters to
native vectors on the server. **The stored column is a vector, not JSON text.**
It supports 1-1,998 dimensions and requires a deployment supporting the
[native SQL vector type](https://learn.microsoft.com/en-us/sql/t-sql/data-types/vector-data-type).
There is no automatic JSON-column fallback or embedding generation. Use SQLAlchemy
`JSON` columns when your mapped metadata includes dictionaries or lists.

For **Search chunks with SQL metadata**, using an open `chunk_search_client`
configured for the chunk index:

```python
import os

from sqlalchemy.ext.asyncio import create_async_engine


engine = create_async_engine(os.environ["AZURE_SQL_URL"])
try:
    async with engine.begin() as connection:
        markdown_store = AzureAISearchStore(chunk_search_client, chunk_index)
        metadata_store = AzureSQLStore(connection, metadata_table)
        pipeline = Pipeline(converter, chunker, embeddings, markdown_store=markdown_store, metadata_store=metadata_store)
        result = await ingest_document(data, "document-1", pipeline)
finally:
    await engine.dispose()
```

For the reverse arrangement, choose `AzureSQLStore(connection, chunk_table)` and
`AzureAISearchStore(metadata_search_client, metadata_index)`, using an open client
for that metadata index. For both roles in SQL, create
two SQL stores on the same connection inside `engine.begin()`.

- Tables must already exist. Defining `Table` objects does not provision them.
  Schemas, indexes, credentials, migrations, and relationships belong to the caller.
- Tables require primary keys; composite keys are supported. Every mapped row
  must supply all primary-key values, and unknown mapped columns are rejected.
  Dictionary keys use SQLAlchemy `Column.key`, which may differ from the
  database column name when aliases are declared.
- Writes require an **active caller-owned transaction**. `engine.begin()` commits
  on successful exit and rolls back on errors. Store methods never commit,
  roll back, or close the connection themselves.
- Upserts use bound values, SQLAlchemy-quoted identifiers, and primary-key lookups
  with SQL Server `UPDLOCK, HOLDLOCK` hints to protect the subsequent insert or
  update. Updates change supplied non-key fields; omitted columns remain unchanged.
  Locks last until the transaction ends, and database errors propagate.
- Both SQL roles can commit together on a shared connection. **No transaction
  spans SQL and Search**: one backend can succeed while the other fails. Use
  stable keys and coordinate retries, rollback, and obsolete-chunk cleanup in
  application code.

### Migrating the combined store API

The former `BaseStore` and combined `store(result, ...)` API are replaced by the
two role-specific bases and methods. Construct each provider with only its own
index or table, then pass `result.chunks` to `store_markdown` and `result.metadata`
to `store_metadata`. Mappers still own complete document fields and identifiers.

## Extending Ingestra

Implement a public interface and pass your instance to `Pipeline`. Components
can live in your own application or package; no plugin registry or pipeline
modification is required.

| Extension point                                          | Method to implement                                                  | Contract                                                                    |
|----------------------------------------------------------|----------------------------------------------------------------------|-----------------------------------------------------------------------------|
| [Converter](../src/ingestra/converter/base.py)           | `async convert(data: bytes) -> tuple[str, dict[str, object]]`        | Return Markdown and document metadata; reject unsupported inputs explicitly |
| [Chunker](../src/ingestra/chunker/base.py)               | `chunk(text: str, /) -> list[Chunk]`                                 | Return chunks in source order; use `[]` for blank text                      |
| [Embedding provider](../src/ingestra/embeddings/base.py) | `async generate(texts: Sequence[str]) -> list[list[float]]`          | Return one vector per input in the same order; never silently truncate      |
| [Markdown store](../src/ingestra/store/markdown/base.py) | `async _store_documents(documents: list[dict[str, object]]) -> None` | Persist the complete documents produced by the base class's chunk mapper    |
| [Metadata store](../src/ingestra/store/metadata/base.py) | `async _store_documents(documents: list[dict[str, object]]) -> None` | Persist the complete document produced by the base class's metadata mapper  |

For example, an application that already receives UTF-8 Markdown can bypass
cloud conversion:

```python
"""Provide a converter for documents that are already UTF-8 Markdown."""

from ingestra.converter import BaseConverter


class Utf8MarkdownConverter(BaseConverter):
    """Decode Markdown bytes without calling a conversion service."""

    async def convert(self, data: bytes) -> tuple[str, dict[str, object]]:
        """Return decoded Markdown and its content type.

        Args:
            data: UTF-8 Markdown document bytes.

        Returns:
            Markdown text and document-level content type metadata.

        Raises:
            TypeError: The input is not bytes.
            UnicodeDecodeError: The document is not valid UTF-8.
        """
        if not isinstance(data, bytes):
            raise TypeError("data must be bytes")
        return data.decode("utf-8"), {"content_type": "text/markdown"}
```

Replace the converter in the end-to-end example with
`converter = Utf8MarkdownConverter()` and keep your chosen chunker and embedding
provider. The Azure OpenAI provider still makes network requests; replacing the
converter does not make the whole pipeline offline.

When implementing another provider:

1. Keep configuration and client construction outside the pipeline.
2. Preserve the relevant interface's validation, empty-input behavior, result
   ordering, and error propagation.
3. For stores, implement the protected persistence hook and reuse the base
   class's public mapping methods. Subclass both storage bases only if your
   backend supports both roles.
4. Add tests under [tests](../tests/) for successful processing, invalid inputs,
   empty inputs, and provider failures. Use `unittest.TestCase` for synchronous
   behavior and `unittest.IsolatedAsyncioTestCase` for async behavior.
5. Run the [test suite](#tests) and update documentation for the new component.

## Local development setup

Clone the repository and synchronize its declared dependencies:

```powershell
git clone https://github.com/krprashantpk/ingestra.git
Set-Location .\ingestra
uv sync
uv run python -c "import ingestra; print(ingestra.__version__)"
```

If you already have a checkout, run the last two commands from its root.
`uv sync` creates or reuses the root `.venv` and installs the project in editable
mode, so changes under [src/ingestra](../src/ingestra/) are available without
reinstalling. Run Python commands with `uv run`; do not create another virtual
environment.

For VS Code, open the repository root and select
`.venv\Scripts\python.exe` as the interpreter on Windows. Read the repository's
[coding conventions](../AGENTS.md) before making changes.

Run the [unit tests](#tests), try the [local quick start](#chunk-markdown-without-azure),
and [build the package](#build). The library itself has no local server to
start and no required environment configuration for mocked tests. Azure
environment variables are needed only when running examples that call Azure;
the library does not automatically load a `.env` file.

### Develop the Functions sample

The Functions runtime dependency is in the optional `samples` dependency group.
From the repository root:

```powershell
uv sync --group samples
Push-Location .\samples\contract-ingestion
try {
    uv run --project ..\.. --group samples python -m unittest discover -s tests -v
}
finally {
    Pop-Location
}
```

These sample tests mock external services. Running the Function host locally
also needs Azure Functions Core Tools v4, Azurite for host storage, provisioned
Azure endpoints, and SQL connectivity with ODBC Driver 18. Copy and configure
the sample's [local settings template](../samples/contract-ingestion/local.settings.json.example)
before starting the host. Local HTTP hosting still calls the configured Azure
services; Azurite does not replace document conversion, embeddings, or SQL.

## Azure Functions sample

The [contract-ingestion sample](../samples/contract-ingestion/README.md) is a
complete application with a Function-key-protected HTTP endpoint and an
Event Grid Blob trigger. Both use `Pipeline.ingest()` to persist chunks,
native embeddings, page numbers, and metadata in Azure SQL.

Its guide covers infrastructure, authentication, deployment, requests, and
local HTTP debugging. Bicep templates and a PowerShell deployment script are
included. Deploying the sample creates billable Azure resources; it is not
required to install the library or run the unit tests.

## Project structure

| Location                                                     | Purpose                                                       |
|--------------------------------------------------------------|---------------------------------------------------------------|
| [src/ingestra](../src/ingestra/)                             | Library implementation and public component interfaces        |
| [pipeline.py](../src/ingestra/pipeline.py)                   | Conversion, chunking, embedding, and optional storage flow    |
| [types.py](../src/ingestra/types.py)                         | Shared result models                                          |
| [tests](../tests/)                                           | Library unit tests                                            |
| [samples/contract-ingestion](../samples/contract-ingestion/) | Azure Functions application, infrastructure, and sample tests |
| [pyproject.toml](../pyproject.toml)                          | Package metadata, Python requirement, and dependency groups   |
| [uv.lock](../uv.lock)                                        | Resolved dependency versions                                  |
| [architecture.md](../architecture.md)                        | Component boundaries, storage semantics, and design details   |
| [AGENTS.md](../AGENTS.md)                                    | Repository development conventions                            |

## Tests

Pipeline and storage tests exercise both contracts, optional roles, ingestion
write ordering, all four backend combinations through ingestion, SDK
serialization, SQL compilation, native vector parameter processing, and failure
handling without service credentials. They do not connect to a live Azure SQL
database or Search service.

```powershell
uv run python -m unittest discover -s tests -v
```

> [!NOTE]
> The saved-document regression test requires the original 18-page fixture at
> `tests\chunkers\markdowns\redp5110_sampled.md`, which is not included in this
> checkout. Without it, that test is explicitly skipped. The separate
> experiment-sample test is skipped when its optional local document is absent.
> See [the chunker tests](../tests/test_markdown_chunker.py) for these cases.

## Build

The package uses uv's native `uv_build` backend, which supports the `src` layout
without generating setuptools `.egg-info` directories in the source tree.
From the repository root:

```powershell
uv build
```

This creates a wheel and source distribution in `dist/`.
