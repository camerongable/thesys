# Retrieval Pipeline

The retrieval pipeline turns project evidence into bounded, cited context for AI workflows.

## Pipeline

```text
source ingestion
→ extraction and provenance metadata
→ chunking
→ embedding
→ project-scoped retrieval
→ query planning and subqueries
→ result fusion
→ reranking
→ context assembly
→ citation IDs and quality diagnostics
```

## Ingestion

Evidence can come from notes, transcripts, URLs, discovered source snapshots, text files, Markdown files, PDFs, and images.

`evidence_service.py` handles storage and chunking. `source_provenance_service.py` handles canonical URLs, content hashes, fetched-page prompt-injection markers, fetch failure categories, PDF page lineage, and quality signals. `multimodal_extraction_service.py` provides deterministic local extraction and optional LiteLLM multimodal extraction for images and low-text PDFs.

## Retrieval

`retrieval_service.py` supports semantic, keyword, and hybrid modes. In live PostgreSQL mode it can use pgvector-backed similarity search. In local SQLite or fallback mode it uses application-side scoring so tests and demos remain deterministic.

Retrieval diagnostics include:

- embedding provider, model, dimension, version
- vector index availability
- query plan and subqueries
- candidate count and latency
- reranker provider and fallback status
- context token budget and selected count
- dedupe/drop counts
- citation coverage, recall, and precision proxies

## Context Assembly

The context assembler enforces:

- token budget
- max chunks per source
- minimum score
- near-duplicate text removal
- source diversity
- citation ID preservation

Retrieved content is untrusted factual evidence. Prompt builders must not treat retrieved text as instructions.
