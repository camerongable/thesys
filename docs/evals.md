# Evals

This document describes product-facing evaluation endpoints and their historical
milestones. The current developer/CI evaluation map is
[Evals And Observability](EVALS_AND_OBSERVABILITY.md); security and adversarial
verification is summarized in [Security And Evals](SECURITY_AND_EVALS.md).

Evaluation is part of the MVP. AI workflow executions are persisted in
`ai_runs` and `ai_steps`, and Sprint 8 adds the first local MVP readiness check.
Sprint 10 keeps this eval as a developer/demo check but replaces the primary
user-facing Overview language with computed Idea Readiness.

Run the seeded-demo eval:

```bash
curl -X POST http://localhost:8000/api/demo/seed
curl http://localhost:8000/api/projects/<project_id>/evals/mvp
```

The MVP eval currently checks:

- structured project state
- ready evidence source count
- current opportunity brief
- required brief sections
- claim-to-evidence citation links
- unsupported/open claims
- competitor landscape coverage
- assumptions and risks
- validation artifact, experiment, and result
- decision traceability
- workflow observability

This remains intentionally lightweight for a seeded demo. The repository now
also includes fixture datasets, retrieval/citation checks, prompt/model approval
tests, Promptfoo adversarial cases, and cost/latency reporting; see the linked
evaluation documentation for their current commands and limits.

## V1 Research Eval

V1 adds a local research-sprint eval dataset at
`apps/api/app/evals/research_sprint_cases.json`. It covers 10 idea categories:
consumer app, B2B SaaS, developer tool, marketplace, health/fitness, local
services, AI workflow, creator economy, productivity, and ecommerce/affiliate.
Five cases are marked demo-ready.

Run the V1 research eval:

```bash
curl http://localhost:8000/api/projects/<project_id>/evals/v1-research
```

The V1 eval checks:

- research sprint existence and completion/reviewability
- source candidate discovery and ingestion
- competitor candidate discovery and merging
- cited research memo coverage
- unsupported/open claim tracking
- research-derived assumptions and risks
- recommended validation actions
- agentic workflow traceability and stored tool calls
- evidence gap detection
- token/cost and latency visibility
