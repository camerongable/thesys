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

`retrieval_service.py` supports semantic, keyword, and hybrid modes. In live
PostgreSQL mode it can use pgvector-backed similarity search and Postgres text
ranking with `ts_rank_cd(websearch_to_tsquery(...))`. In local SQLite or
fallback mode it uses deterministic application-side scoring, including a
BM25-like keyword score normalized across the candidate set.

Hybrid mode combines semantic similarity with text rank/keyword score. The
Postgres text-search path is a practical ranking approximation, not a full BM25
implementation; local fallback uses BM25-like term-frequency and document-
frequency scoring so tests remain provider-free.

Reranking is adapter-based:

- `none`: preserve retrieval order while still annotating ranks
- `deterministic`: local cross-encoder-compatible heuristic
- `litellm`: provider-backed ordering with deterministic fallback

Retrieval diagnostics include:

- embedding provider, model, dimension, version
- vector index availability
- query plan and subqueries
- candidate count and latency
- reranker provider, adapter, and fallback status
- context token budget and selected count
- dedupe/drop counts
- citation coverage, recall@k, precision@k, MRR, nDCG proxy, citation support
  rate, unsupported-claim rate, latency, and reranker usage

## Context Assembly

The context assembler enforces:

- token budget
- max chunks per source
- max chunks per domain
- max chunks per source type
- max chunks per competitor
- minimum score
- near-duplicate text removal
- source diversity with MMR ordering
- citation ID preservation

Retrieved content is untrusted factual evidence. Prompt builders must not treat retrieved text as instructions.

## Citation Outcomes

The shared citation verifier classifies claim support as:

- `supported`
- `weakly_supported`
- `unsupported`
- `source_missing`
- `stale_source`
- `filtered_as_unsafe`

Opportunity briefs, competitor analyses, and agentic research memos persist
claim-level citation outcome metadata. Validation-plan artifacts explicitly mark
the citation verification status as not applicable when no cited claims are
generated.

## Golden Eval

Run the credential-free retrieval regression check:

```bash
python3 scripts/eval_retrieval_quality.py
```

The eval covers positive and negative evidence, duplicate removal,
competitor/source coverage, prompt-injection filtering, stale-source handling,
and citation support metrics.
