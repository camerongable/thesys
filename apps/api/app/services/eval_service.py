import uuid
from dataclasses import dataclass
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.core.auth import AuthContext
from app.db.models import (
    AIRun,
    Artifact,
    Assumption,
    Claim,
    ClaimEvidenceLink,
    Competitor,
    Decision,
    EvidenceSource,
    Experiment,
    ExperimentResult,
    Risk,
)
from app.schemas.evals import MvpEvalCheckRead, MvpEvalRead
from app.services import project_service

REQUIRED_BRIEF_SECTIONS = (
    "Executive Summary",
    "Product Hypothesis",
    "Target User / Buyer",
    "Problem Analysis",
    "Current Alternatives",
    "Competitor Landscape",
    "Risks and Kill-Risk Assumptions",
    "Validation Plan",
    "Unsupported Claims / Open Questions",
)


@dataclass(frozen=True)
class _Check:
    key: str
    label: str
    passed: bool
    observed: int | bool | str | None
    expected: str


def run_mvp_eval(db: Session, auth: AuthContext, project_id: uuid.UUID) -> MvpEvalRead:
    project = project_service.get_project(db, auth, project_id)
    counts = _counts(db, auth, project_id)
    brief = _current_artifact(db, auth, project_id, "opportunity_brief")
    competitor_artifact = _current_artifact(db, auth, project_id, "competitor_landscape")
    validation_artifact = _current_artifact(db, auth, project_id, "validation_plan")
    brief_version = _current_version(brief)
    markdown = brief_version.markdown_content if brief_version else ""
    structured = brief_version.structured_content if brief_version else {}
    unsupported = structured.get("unsupported_claims") if isinstance(structured, dict) else []

    checks = [
        _Check(
            "structured_project_state",
            "Structured project state",
            bool(project.current_thesis_id and (project.customer_segments or project.problems)),
            bool(project.current_thesis_id and (project.customer_segments or project.problems)),
            "current thesis plus segment or problem records",
        ),
        _Check(
            "evidence_sources",
            "Evidence sources",
            counts["ready_evidence_sources"] >= 3,
            counts["ready_evidence_sources"],
            "at least 3 ready sources",
        ),
        _Check(
            "opportunity_brief",
            "Opportunity brief artifact",
            brief_version is not None,
            bool(brief_version),
            "current opportunity brief version",
        ),
        _Check(
            "brief_sections",
            "Required brief sections",
            _contains_required_sections(markdown),
            _section_coverage(markdown),
            "all required MVP brief sections",
        ),
        _Check(
            "citation_coverage",
            "Citation links",
            counts["claim_evidence_links"] >= 1,
            counts["claim_evidence_links"],
            "at least 1 claim linked to evidence",
        ),
        _Check(
            "unsupported_claims",
            "Unsupported claims are visible",
            isinstance(unsupported, list) and len(unsupported) >= 1,
            len(unsupported) if isinstance(unsupported, list) else 0,
            "at least 1 unsupported/open claim",
        ),
        _Check(
            "competitor_landscape",
            "Competitor landscape",
            counts["competitors"] >= 3 and competitor_artifact is not None,
            counts["competitors"],
            "at least 3 competitors and a landscape artifact",
        ),
        _Check(
            "assumptions_risks",
            "Assumptions and risks",
            counts["assumptions"] >= 2 and counts["risks"] >= 1,
            f"{counts['assumptions']} assumptions, {counts['risks']} risks",
            "at least 2 assumptions and 1 risk",
        ),
        _Check(
            "validation_loop",
            "Validation loop",
            counts["experiments"] >= 1
            and counts["experiment_results"] >= 1
            and validation_artifact is not None,
            f"{counts['experiments']} experiments, {counts['experiment_results']} results",
            "validation artifact, experiment, and logged result",
        ),
        _Check(
            "decision_traceability",
            "Decision traceability",
            counts["decisions"] >= 1,
            counts["decisions"],
            "at least 1 decision record",
        ),
        _Check(
            "workflow_observability",
            "Workflow observability",
            counts["ai_runs"] >= 1,
            counts["ai_runs"],
            "at least 1 AI/workflow run trace",
        ),
    ]
    score = sum(1 for check in checks if check.passed)
    return MvpEvalRead(
        project_id=project.id,
        passed=score == len(checks),
        score=score,
        total=len(checks),
        checks=[
            MvpEvalCheckRead(
                key=check.key,
                label=check.label,
                passed=check.passed,
                observed=check.observed,
                expected=check.expected,
            )
            for check in checks
        ],
    )


def _counts(db: Session, auth: AuthContext, project_id: uuid.UUID) -> dict[str, int]:
    filters: dict[str, Any] = {"workspace_id": auth.workspace_id, "project_id": project_id}
    return {
        "ready_evidence_sources": _count(
            db,
            select(func.count())
            .select_from(EvidenceSource)
            .where(
                EvidenceSource.workspace_id == filters["workspace_id"],
                EvidenceSource.project_id == filters["project_id"],
                EvidenceSource.ingestion_status == "ready",
            ),
        ),
        "artifacts": _model_count(db, Artifact, filters),
        "competitors": _model_count(db, Competitor, filters),
        "assumptions": _model_count(db, Assumption, filters),
        "risks": _model_count(db, Risk, filters),
        "experiments": _model_count(db, Experiment, filters),
        "experiment_results": _model_count(db, ExperimentResult, filters),
        "decisions": _model_count(db, Decision, filters),
        "ai_runs": _model_count(db, AIRun, filters),
        "claim_evidence_links": _count(
            db,
            select(func.count())
            .select_from(ClaimEvidenceLink)
            .join(Claim, ClaimEvidenceLink.claim_id == Claim.id)
            .where(Claim.workspace_id == auth.workspace_id, Claim.project_id == project_id),
        ),
    }


def _model_count(db: Session, model: type, filters: dict[str, Any]) -> int:
    return _count(
        db,
        select(func.count())
        .select_from(model)
        .where(
            model.workspace_id == filters["workspace_id"],
            model.project_id == filters["project_id"],
        ),
    )


def _count(db: Session, stmt) -> int:
    return int(db.scalar(stmt) or 0)


def _current_artifact(
    db: Session,
    auth: AuthContext,
    project_id: uuid.UUID,
    artifact_type: str,
) -> Artifact | None:
    artifact = db.scalar(
        select(Artifact)
        .where(
            Artifact.workspace_id == auth.workspace_id,
            Artifact.project_id == project_id,
            Artifact.artifact_type == artifact_type,
        )
        .options(selectinload(Artifact.versions))
        .order_by(Artifact.updated_at.desc())
    )
    if artifact is None or artifact.current_version_id is None:
        return artifact
    return artifact


def _current_version(artifact: Artifact | None):
    if artifact is None or artifact.current_version_id is None:
        return None
    return next(
        (version for version in artifact.versions if version.id == artifact.current_version_id),
        None,
    )


def _contains_required_sections(markdown: str) -> bool:
    return all(section.casefold() in markdown.casefold() for section in REQUIRED_BRIEF_SECTIONS)


def _section_coverage(markdown: str) -> str:
    covered = sum(
        1 for section in REQUIRED_BRIEF_SECTIONS if section.casefold() in markdown.casefold()
    )
    return f"{covered}/{len(REQUIRED_BRIEF_SECTIONS)}"
