# Source Intelligence

Source intelligence captures how evidence was fetched, parsed, extracted,
scored, and cited. V1 is intentionally deterministic in local mode and records
provider-unavailable warnings when live search or multimodal providers are not
configured.

## Source-Linked Pipeline

```text
URL, upload, note, discovered candidate, PDF, or image
-> fetch/upload validation
-> parser or extraction fallback
-> snapshot and provenance metadata
-> chunking and embeddings
-> source-quality scoring
-> retrieval weighting
-> citation and Inspect surfaces
```

Primary owners:

| Concern | Source |
|---|---|
| Ingestion orchestration | `apps/api/app/services/evidence_service.py` |
| Extraction helpers | `apps/api/app/features/evidence/extraction.py` |
| Source provenance | `apps/api/app/features/evidence/source_provenance.py` |
| Source discovery shaping | `apps/api/app/features/research/source_discovery.py` |
| Extraction quality eval | `scripts/eval_extraction_quality.py` |
| Provider-unavailable warning metrics | `apps/api/app/features/evals/provider_warnings.py` |

## Parser Decision

V1 keeps the deterministic parser path as the default fallback. It uses Python
standard-library parsing and deterministic extraction metadata so the portfolio
project can run without external services. A maintained readability dependency
such as `trafilatura` or `readability-lxml` remains a productization backlog
item, not a completed V1 dependency.

Metadata records parser method, parser confidence, content type, response size,
canonical/final URL, prompt-injection markers, source-quality factors, quote
offsets, PDF page lineage, OCR fallback metadata, and provider-unavailable
warnings.

## Snapshot And Screenshot Disposition

V1 records snapshot metadata and extracted text. It does not yet persist true
page screenshots or full page artifacts to durable object storage in local mode.
That is a future productization item that should include storage keys,
retention, redaction policy, backup/restore behavior, and browser QA.

Screenshot-region OCR and screenshot-table provenance are out of V1 unless true
screenshot artifact capture is implemented first.

## Provenance Fields

Common fields include:

- `canonical_url`
- `final_url`
- `domain`
- `fetched_at`
- `response_content_type`
- `response_byte_length`
- `content_hash`
- `source_snapshot_id`
- `parser`
- `parser_confidence`
- `pdf_page_count`
- `pdf_page_lineage`
- `ocr_fallback`
- `table_id`
- `region`
- `quote_offsets`
- `source_quality`
- `warnings`
- `provider`
- `confidence`

Retrieval, Ask Thesys citation drilldowns, research memos, and Evidence Inspect
should preserve these fields where relevant.

## Live Provider QA

Opt-in live provider checks should record provider mode, credentials, rate
limits, egress allowlists, and exact rerun commands. Without credentials, the
eval reports explicit provider-unavailable warnings.

```bash
python3 scripts/eval_extraction_quality.py --json
```

If Tavily or multimodal credentials are configured, rerun the provider-specific
smoke path and record output in `IMPLEMENTATION_STATUS.md`.

## Browser QA

Sprint 60 browser QA should cover:

- Evidence Inspect provenance rows
- retrieval result provenance
- Ask Thesys citation drilldowns
- research memo citations
- source-discovery provenance
- Project Inspect trust summaries
- provider-unavailable warnings
- no homepage or primary workflow clutter

## Current Limits

- Maintained readability parser dependency is intentionally not added in V1.
- True screenshot/page artifact persistence is future owner work.
- Screenshot-region OCR/table provenance is blocked on screenshot persistence.
- Live Tavily and multimodal provider QA require credentials and allowed egress.
