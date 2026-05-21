# Evals

Evaluation is part of the MVP. Sprint 2 adds AI run/step records and a
structured-output smoke test, which gives later prompt and workflow evals a
place to persist execution metadata.

The first eval harness should be added with the evidence ingestion and RAG
sprints. It should track retrieval relevance, citation coverage, unsupported
claim count, groundedness, latency, and cost.
