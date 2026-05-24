# Evals

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

This is intentionally lightweight. Later eval work should add fixture datasets,
retrieval relevance labels, groundedness scoring, prompt regression tests, and
cost/latency thresholds.
