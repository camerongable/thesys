# Data Classification

## Model

Thesys uses four classifications. The code-owned enum and data-type registry
live in `apps/api/app/security/contracts.py`.

| Class | Meaning | Default handling |
| --- | --- | --- |
| `public` | Intentionally public information | May be processed by approved services; integrity and provenance still matter |
| `internal` | Low-sensitivity product or project metadata | Authenticated access; approved providers only |
| `confidential` | User strategy, derived intelligence, and operational records | Tenant scoped, encrypted in transit/at rest, redacted telemetry, approved providers |
| `restricted` | Credentials, direct identifiers, or especially sensitive user content | Least privilege, local-only or explicitly approved restricted-data provider, no raw telemetry |

## Default classifications

| Data type | Default | Provider policy | Owner |
| --- | --- | --- | --- |
| Public web source | Public | Approved provider | EvidenceService |
| Project name or general concept | Internal | Approved provider | ProjectService |
| User identity | Confidential | Local only | IdentityService |
| Workspace membership | Confidential | Local only | IdentityService |
| Business plan, thesis, or strategy | Confidential | Approved provider | ProjectService |
| Uploaded file | Confidential | Approved provider | EvidenceService |
| Raw extracted text | Confidential | Approved provider | EvidenceService |
| Sanitized searchable text | Confidential | Approved provider | RetrievalService |
| Interview notes with names/emails | Restricted | Approved restricted provider | EvidenceService |
| Embeddings derived from project text | Confidential | Approved provider | EmbeddingService |
| Project memory | Confidential | Approved provider | MemoryService |
| Research results and memos | Confidential | Approved provider | ResearchSprintService |
| Validation results | Confidential | Approved provider | ValidationService |
| Decision records | Confidential | Approved provider | ValidationService |
| API credentials | Restricted | Local only | PlatformSecurity |
| OAuth credentials and refresh tokens | Restricted | Local only | PlatformSecurity |
| Wrapped per-workspace data-encryption key | Restricted | Local only | PlatformSecurity |
| System prompts | Confidential | Approved provider | AISafetyGateway |
| Tool schemas | Confidential | Approved provider | ToolPolicyGateway |
| MCP server registrations | Confidential | Local only | ToolPolicyGateway |
| Audit events | Confidential | Local only | GovernanceService |
| Authentication audit events | Confidential | Local only | IdentityService |
| Hashed session revocations | Confidential | Local only | IdentityService |
| LangSmith traces | Same as contained data; confidential by default | Approved provider | ObservabilityService |
| Temporal workflow state | Confidential | Local only | TemporalResearchService |
| Raw model-provider request/response | Confidential or restricted based on payload | Matching approved provider | AISafetyGateway |

The table mirrors `DATA_TYPES`. Changes to classifications must update the code
registry and its tests in the same pull request.

## Handling requirements

| Requirement | Public | Internal | Confidential | Restricted |
| --- | --- | --- | --- | --- |
| Authentication | Optional for source discovery | Required | Required | Required |
| Workspace authorization | When attached to a project | Required | Required | Required |
| Encryption in transit | Required | Required | Required | Required |
| Encryption at rest | Recommended | Required | Required | Required with managed keys in production |
| Logs/traces | Metadata allowed | Bounded metadata | Redacted metadata only | No raw value; event metadata only |
| External provider | Approved provider | Approved provider | Approved provider | Local only or approved restricted-data provider |
| Retention/deletion | Source policy | Project policy | Project policy | Shortest practical retention and verified deletion |

## Classification rules

1. Derived data inherits the highest classification of its inputs. Embeddings,
   summaries, cache entries, traces, and eval fixtures are not automatically less
   sensitive than the source text.
2. A data set containing credentials or direct identifiers is `restricted`, even
   if the surrounding document would otherwise be `confidential`.
3. Public source content becomes tenant-scoped project data after ingestion;
   provenance stays public, while annotations and analysis are confidential.
4. Redaction does not downgrade classification. It only reduces exposure in a
   particular representation.
5. Unknown data is treated as `confidential` until classified. Unknown content
   with likely credentials or direct identifiers is treated as `restricted`.

## Detection pipeline

The ingestion and provider-redaction paths combine deterministic credential and
common-identifier recognizers with Presidio rule recognizers for extended
identifier formats such as SSNs, IBANs, bank accounts, passports, and IP
addresses. Presidio runs against a local blank tokenizer for this baseline, so
the application never downloads an NLP model at request time. Its spans are
merged with the deterministic results before classification and anonymization.

## Provider decisions

Before external egress, the caller must know the effective classification,
provider identity, allowed purpose, and retention/training policy. A missing
classification or provider policy is a denial, not a fallback to unrestricted
processing. Sprint 62 implements provider/tenant policy; Sprints 63-64 add
payload-aware classification and DLP enforcement.

### Current outbound routes

- LiteLLM chat and embedding payloads pass through the same purpose-aware
  policy and deterministic redaction before egress.
- Tavily receives a separately policy-bound, redacted external-search query;
  it is limited to `internal` data after sanitization.
- Live LiteLLM multimodal extraction permits a raw file only when local
  byte-level inspection and filename sanitization require no redaction.
  Detected text identifiers or secrets deny the upload rather than sending a
  partially sanitized file. Image-only and complex document detection remain
  subject to the secure-ingestion MIME/OCR coverage work.

## Traces, caches, and deletion

- LangSmith traces inherit the highest classification in their payload and must
  be redacted before export.
- Semantic caches inherit source classification and tenant scope. Cache hits may
  not cross workspace, model-policy, prompt-version, or classification boundaries.
- Deleting a source must eventually remove or tombstone raw files, extracted
  text, chunks, embeddings, derived cache entries, and unsupported memory derived
  solely from that source.
