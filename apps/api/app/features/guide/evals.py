"""Guide eval read-model shaping."""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from app.schemas.evals import GuideEvalMetricRead, GuideEvalRead


@dataclass(frozen=True)
class GuideEvalCounts:
    guide_runs: int
    retrieval_steps: int
    proposal_invocations: int
    write_invocations: int


def guide_eval_metrics(counts: GuideEvalCounts) -> list[GuideEvalMetricRead]:
    return [
        GuideEvalMetricRead(
            key="guide_runs",
            label="Guide runs exist",
            passed=counts.guide_runs >= 1,
            observed=counts.guide_runs,
            expected="at least one guide_chat run",
        ),
        GuideEvalMetricRead(
            key="guide_retrieval",
            label="Guide retrieval grounding",
            passed=counts.retrieval_steps >= 1,
            observed=counts.retrieval_steps,
            expected="at least one guide retrieval context step",
        ),
        GuideEvalMetricRead(
            key="proposal_governance",
            label="Proposal governance",
            passed=counts.proposal_invocations >= 0 and counts.write_invocations == 0,
            observed=(
                f"{counts.proposal_invocations} proposals, "
                f"{counts.write_invocations} direct writes"
            ),
            expected="chat creates proposals only, no direct write tools",
        ),
    ]


def guide_eval_read(project_id: uuid.UUID, counts: GuideEvalCounts) -> GuideEvalRead:
    metrics = guide_eval_metrics(counts)
    score = sum(1 for metric in metrics if metric.passed)
    return GuideEvalRead(
        project_id=project_id,
        passed=score == len(metrics),
        score=score,
        total=len(metrics),
        metrics=metrics,
    )
