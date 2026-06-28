# Retrieval And Citations

Thesys uses retrieval-grounded generation so strategic claims can be traced back
to evidence. Retrieval quality, citation coverage, and unsupported-claim
handling are treated as AI product behavior, not implementation details.

## Source-Linked Pipeline

```text
evidence source
-> extraction and provenance metadata
-> chunks and embeddings
-> query planning
-> semantic, keyword, or hybrid retrieval
-> SQL/vector path or Python fallback
-> result fusion and dedupe
-> reranking
-> context selection with source diversity
-> citation verification
-> cited artifact or guide answer
```

Primary owners:

| Concern | Source |
|---|---|
| Ingestion, chunks, embeddings | `apps/api/app/services/evidence_service.py` |
| Source provenance | `apps/api/app/features/evidence/source_provenance.py` |
| Query planning and tokenization | `apps/api/app/features/retrieval/planning.py` |
| Score math | `apps/api/app/features/retrieval/scoring.py` |
| Result fusion | `apps/api/app/features/retrieval/result_shaping.py` |
| Reranking | `apps/api/app/features/retrieval/reranker.py` |
| Context selection | `apps/api/app/features/retrieval/context_selection.py` |
| Diagnostics | `apps/api/app/features/retrieval/diagnostics.py` |
| Citation verification | `apps/api/app/features/evidence/citation_verifier.py` |

## Ranking Behavior

Retrieval supports semantic, keyword, and hybrid modes. In PostgreSQL mode, the
backend can use pgvector similarity and Postgres text ranking with
`ts_rank_cd(websearch_to_tsquery(...))`. This is BM25-like ranking, not exact
BM25. SQLite/local fallback uses deterministic application-side scoring so
tests and demos do not require provider credentials.

Hybrid scoring combines semantic similarity with keyword/text rank. Reranking
is adapter-based:

- `none`: preserve order and annotate ranks
- `deterministic`: local cross-encoder-compatible heuristic
- `litellm`: provider-backed reranking with deterministic fallback

Context selection applies source/domain/type/competitor caps, near-duplicate
removal, source-quality weighting, MMR ordering, score thresholds, and token
budget limits.

## Cache And Invalidation

Sprint 57 added semantic cache coverage for embeddings, retrieval plans,
rerank results, and optional non-streaming guide answers. Cache keys are
workspace/project scoped and include version inputs so stale records can be
denied instead of silently reused. Eval reports surface cache hit/miss/stale
denial, saved token/cost, and latency metrics.

Provider or reranker changes should update cache version inputs and the docs
for invalidation behavior.

## Citation Verifier Ownership

| Artifact path | Citation behavior |
|---|---|
| Opportunity briefs | Claim-level citations are verified and weak/unsupported claims are labeled. |
| Competitor analysis | Competitor claims retain retrieved IDs and citation validity metadata. |
| Agentic research memos | Findings, claims, evidence IDs, support status, and open questions are audited. |
| Ask Thesys answers | Citation drilldowns expose source title, URL/file/page, support status, and context IDs. |
| Validation plans | Citation verification can be marked not applicable when the artifact generates no cited claims. |
| Decision recommendations | Evidence labels distinguish missing, weak, and decision-ready support. |

Citation outcomes include `supported`, `weakly_supported`, `unsupported`,
`source_missing`, `stale_source`, and `filtered_as_unsafe`.

## Verification

```bash
cd apps/api && .venv/bin/pytest app/tests/test_evidence.py app/tests/test_citation_verifier.py app/tests/test_retrieval_quality_eval.py app/tests/test_feature_package_boundaries.py -q
python3 scripts/eval_retrieval_quality.py
```

The golden eval covers positive/negative evidence, duplicate removal,
competitor/source coverage, prompt-injection filtering, stale-source handling,
and citation support metrics.

## Adding A Provider Or Reranker

1. Add the provider adapter under `app.features.retrieval` or a provider-owned
   service boundary.
2. Keep provider calls outside pure scoring/context-selection helpers.
3. Add deterministic fallback behavior for local mode.
4. Add cache version inputs and invalidation tests.
5. Add golden retrieval cases for ranking, source diversity, and citation
   support.
6. Update this document and README portfolio language.

## Current Limits

- Exact BM25 is not implemented; Postgres text rank plus local BM25-like
  fallback is the V1 behavior.
- Retrieval execution, SQL/vector access, cache lookup/write, citation
  persistence, and route orchestration remain service-owned until typed
  retrieval execution DTOs are introduced.
- Production embedding providers and cross-encoder rerankers are extension
  points; deterministic local behavior remains the default demo path.
