import json
import uuid
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.core.auth import AuthContext
from app.db.models import (
    AIRun,
    AIStep,
    Artifact,
    ArtifactVersion,
    Assumption,
    Claim,
    ClaimEvidenceLink,
    Competitor,
    CompetitorCandidate,
    Decision,
    DiscoveredSource,
    EvidenceSource,
    Experiment,
    ExperimentResult,
    ResearchSprint,
    Risk,
    ToolInvocation,
)
from app.schemas.evals import (
    AIEvalMetricRead,
    AIEvalRead,
    MvpEvalCheckRead,
    MvpEvalRead,
    GuideEvalMetricRead,
    GuideEvalRead,
    ResearchEvalCaseRead,
    V1ResearchEvalMetricRead,
    V1ResearchEvalRead,
)
from app.services import ai_accounting_service, langsmith_observability_service, project_service

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


@dataclass(frozen=True)
class _ResearchMetric:
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


def run_v1_research_eval(
    db: Session,
    auth: AuthContext,
    project_id: uuid.UUID,
) -> V1ResearchEvalRead:
    project_service.get_project(db, auth, project_id)
    counts = _v1_research_counts(db, auth, project_id)
    latest_memo = _latest_research_memo_version(db, auth, project_id)
    structured = latest_memo.structured_content if latest_memo else {}
    memo = structured.get("memo") if isinstance(structured, dict) else {}
    unsupported = memo.get("unsupported_claims") if isinstance(memo, dict) else []
    validation_actions = (
        memo.get("recommended_validation_actions") if isinstance(memo, dict) else []
    )
    tool_calls = structured.get("tool_calls") if isinstance(structured, dict) else []
    retrieval_diagnostics = (
        structured.get("retrieval_diagnostics") if isinstance(structured, dict) else []
    )
    retrieval_context = structured.get("retrieval_context") if isinstance(structured, dict) else {}
    gaps = structured.get("evidence_gaps") if isinstance(structured, dict) else []
    markdown = latest_memo.markdown_content if latest_memo else ""
    dataset_cases = _research_eval_cases()
    demo_ready_count = sum(1 for case in dataset_cases if case.demo_ready)

    metrics = [
        _ResearchMetric(
            "eval_dataset",
            "Research sprint eval dataset",
            len(dataset_cases) >= 10,
            len(dataset_cases),
            "at least 10 idea categories",
        ),
        _ResearchMetric(
            "demo_cases",
            "Demo-ready research cases",
            demo_ready_count >= 5,
            demo_ready_count,
            "at least 5 demo-ready ideas",
        ),
        _ResearchMetric(
            "research_sprints",
            "Research sprint exists",
            counts["research_sprints"] >= 1,
            counts["research_sprints"],
            "at least 1 research sprint",
        ),
        _ResearchMetric(
            "completed_or_reviewable_sprint",
            "Completed or reviewable sprint",
            counts["completed_sprints"] + counts["needs_review_sprints"] >= 1,
            f"{counts['completed_sprints']} completed, {counts['needs_review_sprints']} reviewable",
            "at least 1 completed or reviewable sprint",
        ),
        _ResearchMetric(
            "source_discovery",
            "Source discovery quality",
            counts["discovered_sources"] >= 3 and counts["ingested_sources"] >= 1,
            f"{counts['discovered_sources']} candidates, {counts['ingested_sources']} ingested",
            "at least 3 candidates and 1 ingested source",
        ),
        _ResearchMetric(
            "external_search_relevance",
            "Search result relevance",
            counts["search_provenance_sources"] >= 1,
            counts["search_provenance_sources"],
            "at least 1 discovered source with search provenance",
        ),
        _ResearchMetric(
            "source_diversity",
            "Source diversity",
            counts["discovered_source_types"] >= 2,
            counts["discovered_source_types"],
            "at least 2 discovered source types",
        ),
        _ResearchMetric(
            "duplicate_detection",
            "Duplicate detection",
            counts["discovered_sources"] == counts["distinct_discovered_urls"],
            (
                f"{counts['distinct_discovered_urls']} distinct URLs / "
                f"{counts['discovered_sources']} candidates"
            ),
            "candidate URLs are deduplicated",
        ),
        _ResearchMetric(
            "provenance_coverage",
            "Provenance coverage",
            counts["sources_with_provenance_metadata"] >= counts["search_provenance_sources"]
            and counts["sources_with_provenance_metadata"] >= 1,
            (
                f"{counts['sources_with_provenance_metadata']} with provenance / "
                f"{counts['discovered_sources']} candidates"
            ),
            "search candidates retain provider/query/rank provenance",
        ),
        _ResearchMetric(
            "competitor_discovery",
            "Competitor discovery quality",
            counts["competitor_candidates"] >= 3 and counts["merged_competitors"] >= 1,
            f"{counts['competitor_candidates']} candidates, {counts['merged_competitors']} merged",
            "at least 3 candidates and 1 merged competitor",
        ),
        _ResearchMetric(
            "cited_research_memo",
            "Cited research memo",
            latest_memo is not None and counts["research_memo_claim_links"] >= 1,
            counts["research_memo_claim_links"],
            "research memo with at least 1 cited claim",
        ),
        _ResearchMetric(
            "research_memo_completeness",
            "Research memo completeness",
            _contains_research_memo_sections(markdown),
            _research_memo_section_coverage(markdown),
            "required V1/Sprint 14 memo sections",
        ),
        _ResearchMetric(
            "unsupported_claims",
            "Unsupported claims tracked",
            isinstance(unsupported, list) and len(unsupported) >= 1,
            len(unsupported) if isinstance(unsupported, list) else 0,
            "at least 1 unsupported/open claim",
        ),
        _ResearchMetric(
            "assumption_quality",
            "Research assumptions and risks",
            counts["high_risk_assumptions"] >= 1 and counts["risks"] >= 1,
            f"{counts['high_risk_assumptions']} high-risk assumptions, {counts['risks']} risks",
            "at least 1 high-risk assumption and 1 risk",
        ),
        _ResearchMetric(
            "validation_actions",
            "Next-action usefulness",
            isinstance(validation_actions, list) and len(validation_actions) >= 1,
            len(validation_actions) if isinstance(validation_actions, list) else 0,
            "at least 1 recommended validation action",
        ),
        _ResearchMetric(
            "agentic_trace",
            "Agentic RAG traceability",
            counts["agentic_research_runs"] >= 1
            and counts["agentic_research_steps"] >= 10
            and isinstance(tool_calls, list)
            and len(tool_calls) >= 3,
            (
                f"{counts['agentic_research_runs']} runs, "
                f"{counts['agentic_research_steps']} steps, "
                f"{len(tool_calls) if isinstance(tool_calls, list) else 0} tool calls"
            ),
            "agentic run, 10+ steps, and stored tool calls",
        ),
        _ResearchMetric(
            "multi_stage_retrieval",
            "Multi-stage retrieval strategy",
            _has_multi_stage_retrieval(retrieval_diagnostics),
            _retrieval_strategy_observed(retrieval_diagnostics),
            "query plan, subqueries, and retrieval diagnostics are stored",
        ),
        _ResearchMetric(
            "reranker_usage",
            "Reranker visibility",
            _has_reranker_diagnostics(retrieval_diagnostics),
            _reranker_observed(retrieval_diagnostics),
            "reranker enabled/disabled state is visible",
        ),
        _ResearchMetric(
            "context_assembly",
            "Context assembly",
            _has_context_assembly(retrieval_context, retrieval_diagnostics),
            _context_assembly_observed(retrieval_context, retrieval_diagnostics),
            "selected context and token budget are visible",
        ),
        _ResearchMetric(
            "retrieval_quality_report",
            "Retrieval quality report",
            _has_quality_report(retrieval_diagnostics),
            _quality_report_observed(retrieval_diagnostics),
            "recall/precision/citation coverage proxies are reported",
        ),
        _ResearchMetric(
            "gap_detection",
            "Evidence gap detection",
            isinstance(gaps, list) and len(gaps) >= 1,
            len(gaps) if isinstance(gaps, list) else 0,
            "at least 1 evidence gap",
        ),
        _ResearchMetric(
            "cost_latency_visible",
            "Cost and latency visibility",
            counts["runs_with_cost"] >= 1 and counts["steps_with_latency"] >= 10,
            (
                f"{counts['runs_with_cost']} runs with cost, "
                f"{counts['steps_with_latency']} steps with latency"
            ),
            "workflow cost and step latency are visible",
        ),
        _ResearchMetric(
            "langsmith_trace_ids",
            "LangSmith trace IDs",
            counts["research_sprints_with_trace"] >= 1
            and counts["agentic_runs_with_trace"] >= 1
            and counts["research_memo_versions_with_trace"] >= 1,
            (
                f"{counts['research_sprints_with_trace']} sprints, "
                f"{counts['agentic_runs_with_trace']} runs, "
                f"{counts['research_memo_versions_with_trace']} memo versions"
            ),
            "trace IDs persisted on sprint, run, and research memo version",
        ),
        _ResearchMetric(
            "langsmith_span_coverage",
            "LangSmith span coverage",
            counts["agentic_steps_with_trace"] >= 10,
            counts["agentic_steps_with_trace"],
            "10+ traced agentic research child steps",
        ),
        _ResearchMetric(
            "secret_redaction",
            "Sensitive value redaction",
            _secret_redaction_check(),
            True,
            "observability sanitizer redacts API keys and tokens",
        ),
    ]
    score = sum(1 for metric in metrics if metric.passed)
    return V1ResearchEvalRead(
        project_id=project_id,
        passed=score == len(metrics),
        score=score,
        total=len(metrics),
        metrics=[
            V1ResearchEvalMetricRead(
                key=metric.key,
                label=metric.label,
                passed=metric.passed,
                observed=metric.observed,
                expected=metric.expected,
            )
            for metric in metrics
        ],
        dataset_cases=dataset_cases,
        dataset_case_count=len(dataset_cases),
        demo_ready_case_count=demo_ready_count,
    )


def run_guide_eval(db: Session, auth: AuthContext, project_id: uuid.UUID) -> GuideEvalRead:
    project_service.get_project(db, auth, project_id)
    guide_runs = int(
        db.scalar(
            select(func.count(AIRun.id)).where(
                AIRun.workspace_id == auth.workspace_id,
                AIRun.project_id == project_id,
                AIRun.workflow_type == "guide_chat",
            )
        )
        or 0
    )
    retrieval_steps = int(
        db.scalar(
            select(func.count(AIStep.id))
            .join(AIRun, AIRun.id == AIStep.ai_run_id)
            .where(
                AIRun.workspace_id == auth.workspace_id,
                AIRun.project_id == project_id,
                AIRun.workflow_type == "guide_chat",
                AIStep.step_name == "guide_retrieval_context",
            )
        )
        or 0
    )
    proposal_invocations = int(
        db.scalar(
            select(func.count(ToolInvocation.id)).where(
                ToolInvocation.workspace_id == auth.workspace_id,
                ToolInvocation.project_id == project_id,
                ToolInvocation.access_mode == "proposal",
                ToolInvocation.requested_by == "agent",
            )
        )
        or 0
    )
    write_invocations = int(
        db.scalar(
            select(func.count(ToolInvocation.id)).where(
                ToolInvocation.workspace_id == auth.workspace_id,
                ToolInvocation.project_id == project_id,
                ToolInvocation.access_mode == "write",
                ToolInvocation.requested_by == "agent",
            )
        )
        or 0
    )
    metrics = [
        _ResearchMetric(
            "guide_runs",
            "Guide runs exist",
            guide_runs >= 1,
            guide_runs,
            "at least one guide_chat run",
        ),
        _ResearchMetric(
            "guide_retrieval",
            "Guide retrieval grounding",
            retrieval_steps >= 1,
            retrieval_steps,
            "at least one guide retrieval context step",
        ),
        _ResearchMetric(
            "proposal_governance",
            "Proposal governance",
            proposal_invocations >= 0 and write_invocations == 0,
            f"{proposal_invocations} proposals, {write_invocations} direct writes",
            "chat creates proposals only, no direct write tools",
        ),
    ]
    score = sum(1 for metric in metrics if metric.passed)
    return GuideEvalRead(
        project_id=project_id,
        passed=score == len(metrics),
        score=score,
        total=len(metrics),
        metrics=[
            GuideEvalMetricRead(
                key=metric.key,
                label=metric.label,
                passed=metric.passed,
                observed=metric.observed,
                expected=metric.expected,
            )
            for metric in metrics
        ],
    )


def run_ai_eval(
    db: Session,
    auth: AuthContext,
    settings: Any,
    project_id: uuid.UUID,
) -> AIEvalRead:
    report = ai_accounting_service.project_ai_cost_report(db, auth, settings, project_id)
    metrics = [
        _ResearchMetric(
            "ai_runs_recorded",
            "AI runs recorded",
            report.run_count >= 1,
            report.run_count,
            "at least one AI run",
        ),
        _ResearchMetric(
            "latency_visible",
            "Step latency visible",
            report.step_count == 0 or report.average_step_latency_ms >= 0,
            report.average_step_latency_ms,
            "average step latency can be computed",
        ),
        _ResearchMetric(
            "budget_status",
            "Budget status",
            report.budget_status == "within_budget",
            report.budget_status,
            "within configured token/cost budget",
        ),
        _ResearchMetric(
            "provider_circuit",
            "Provider circuit breaker",
            report.circuit_breaker_status == "closed",
            report.circuit_breaker_status,
            "provider failure threshold not reached",
        ),
    ]
    score = sum(1 for metric in metrics if metric.passed)
    return AIEvalRead(
        project_id=project_id,
        passed=score == len(metrics),
        score=score,
        total=len(metrics),
        metrics=[
            AIEvalMetricRead(
                key=metric.key,
                label=metric.label,
                passed=metric.passed,
                observed=metric.observed,
                expected=metric.expected,
            )
            for metric in metrics
        ],
        report={
            "run_count": report.run_count,
            "step_count": report.step_count,
            "failed_run_count": report.failed_run_count,
            "total_tokens": report.total_tokens,
            "total_cost": str(report.total_cost),
            "average_step_latency_ms": report.average_step_latency_ms,
            "budget_status": report.budget_status,
            "circuit_breaker_status": report.circuit_breaker_status,
            "workflow_breakdown": report.workflow_breakdown,
        },
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


def _v1_research_counts(db: Session, auth: AuthContext, project_id: uuid.UUID) -> dict[str, int]:
    return {
        "research_sprints": _count(
            db,
            select(func.count())
            .select_from(ResearchSprint)
            .where(
                ResearchSprint.workspace_id == auth.workspace_id,
                ResearchSprint.project_id == project_id,
            ),
        ),
        "completed_sprints": _count(
            db,
            select(func.count())
            .select_from(ResearchSprint)
            .where(
                ResearchSprint.workspace_id == auth.workspace_id,
                ResearchSprint.project_id == project_id,
                ResearchSprint.status == "completed",
            ),
        ),
        "needs_review_sprints": _count(
            db,
            select(func.count())
            .select_from(ResearchSprint)
            .where(
                ResearchSprint.workspace_id == auth.workspace_id,
                ResearchSprint.project_id == project_id,
                ResearchSprint.status == "needs_review",
            ),
        ),
        "discovered_sources": _count(
            db,
            select(func.count())
            .select_from(DiscoveredSource)
            .where(
                DiscoveredSource.workspace_id == auth.workspace_id,
                DiscoveredSource.project_id == project_id,
            ),
        ),
        "ingested_sources": _count(
            db,
            select(func.count())
            .select_from(DiscoveredSource)
            .where(
                DiscoveredSource.workspace_id == auth.workspace_id,
                DiscoveredSource.project_id == project_id,
                DiscoveredSource.status == "ingested",
            ),
        ),
        "search_provenance_sources": _count(
            db,
            select(func.count())
            .select_from(DiscoveredSource)
            .where(
                DiscoveredSource.workspace_id == auth.workspace_id,
                DiscoveredSource.project_id == project_id,
                DiscoveredSource.search_provider.is_not(None),
            ),
        ),
        "sources_with_provenance_metadata": _count(
            db,
            select(func.count())
            .select_from(DiscoveredSource)
            .where(
                DiscoveredSource.workspace_id == auth.workspace_id,
                DiscoveredSource.project_id == project_id,
                DiscoveredSource.search_provider.is_not(None),
                DiscoveredSource.search_query.is_not(None),
                DiscoveredSource.search_result_rank.is_not(None),
            ),
        ),
        "discovered_source_types": _count(
            db,
            select(func.count(func.distinct(DiscoveredSource.source_type)))
            .select_from(DiscoveredSource)
            .where(
                DiscoveredSource.workspace_id == auth.workspace_id,
                DiscoveredSource.project_id == project_id,
            ),
        ),
        "distinct_discovered_urls": _count(
            db,
            select(func.count(func.distinct(DiscoveredSource.url)))
            .select_from(DiscoveredSource)
            .where(
                DiscoveredSource.workspace_id == auth.workspace_id,
                DiscoveredSource.project_id == project_id,
            ),
        ),
        "competitor_candidates": _count(
            db,
            select(func.count())
            .select_from(CompetitorCandidate)
            .where(
                CompetitorCandidate.workspace_id == auth.workspace_id,
                CompetitorCandidate.project_id == project_id,
            ),
        ),
        "merged_competitors": _count(
            db,
            select(func.count())
            .select_from(CompetitorCandidate)
            .where(
                CompetitorCandidate.workspace_id == auth.workspace_id,
                CompetitorCandidate.project_id == project_id,
                CompetitorCandidate.status == "merged",
            ),
        ),
        "research_memo_claim_links": _count(
            db,
            select(func.count())
            .select_from(ClaimEvidenceLink)
            .join(Claim, ClaimEvidenceLink.claim_id == Claim.id)
            .join(ArtifactVersion, ArtifactVersion.id == Claim.artifact_version_id)
            .join(Artifact, Artifact.id == ArtifactVersion.artifact_id)
            .where(
                Claim.workspace_id == auth.workspace_id,
                Claim.project_id == project_id,
                Artifact.artifact_type == "research_memo",
            ),
        ),
        "high_risk_assumptions": _count(
            db,
            select(func.count())
            .select_from(Assumption)
            .where(
                Assumption.workspace_id == auth.workspace_id,
                Assumption.project_id == project_id,
                (
                    Assumption.kill_risk.is_(True)
                    | (
                        Assumption.importance.in_(["high", "critical"])
                        & (Assumption.uncertainty == "high")
                    )
                ),
            ),
        ),
        "risks": _model_count(
            db,
            Risk,
            {"workspace_id": auth.workspace_id, "project_id": project_id},
        ),
        "agentic_research_runs": _count(
            db,
            select(func.count())
            .select_from(AIRun)
            .where(
                AIRun.workspace_id == auth.workspace_id,
                AIRun.project_id == project_id,
                AIRun.workflow_type == "agentic_research",
            ),
        ),
        "agentic_research_steps": _count(
            db,
            select(func.count())
            .select_from(AIStep)
            .join(AIRun, AIStep.ai_run_id == AIRun.id)
            .where(
                AIRun.workspace_id == auth.workspace_id,
                AIRun.project_id == project_id,
                AIRun.workflow_type == "agentic_research",
            ),
        ),
        "runs_with_cost": _count(
            db,
            select(func.count())
            .select_from(AIRun)
            .where(
                AIRun.workspace_id == auth.workspace_id,
                AIRun.project_id == project_id,
                AIRun.workflow_type == "agentic_research",
                AIRun.total_cost.is_not(None),
            ),
        ),
        "steps_with_latency": _count(
            db,
            select(func.count())
            .select_from(AIStep)
            .join(AIRun, AIStep.ai_run_id == AIRun.id)
            .where(
                AIRun.workspace_id == auth.workspace_id,
                AIRun.project_id == project_id,
                AIRun.workflow_type == "agentic_research",
                AIStep.latency_ms.is_not(None),
            ),
        ),
        "research_sprints_with_trace": _count(
            db,
            select(func.count())
            .select_from(ResearchSprint)
            .where(
                ResearchSprint.workspace_id == auth.workspace_id,
                ResearchSprint.project_id == project_id,
                ResearchSprint.langsmith_trace_id.is_not(None),
            ),
        ),
        "agentic_runs_with_trace": _count(
            db,
            select(func.count())
            .select_from(AIRun)
            .where(
                AIRun.workspace_id == auth.workspace_id,
                AIRun.project_id == project_id,
                AIRun.workflow_type == "agentic_research",
                AIRun.langsmith_trace_id.is_not(None),
            ),
        ),
        "agentic_steps_with_trace": _count(
            db,
            select(func.count())
            .select_from(AIStep)
            .join(AIRun, AIStep.ai_run_id == AIRun.id)
            .where(
                AIRun.workspace_id == auth.workspace_id,
                AIRun.project_id == project_id,
                AIRun.workflow_type == "agentic_research",
                AIStep.langsmith_trace_id.is_not(None),
            ),
        ),
        "research_memo_versions_with_trace": _count(
            db,
            select(func.count())
            .select_from(ArtifactVersion)
            .join(Artifact, ArtifactVersion.artifact_id == Artifact.id)
            .where(
                Artifact.workspace_id == auth.workspace_id,
                Artifact.project_id == project_id,
                Artifact.artifact_type == "research_memo",
                ArtifactVersion.langsmith_trace_id.is_not(None),
            ),
        ),
    }


def _latest_research_memo_version(
    db: Session,
    auth: AuthContext,
    project_id: uuid.UUID,
) -> ArtifactVersion | None:
    return db.scalar(
        select(ArtifactVersion)
        .join(Artifact, ArtifactVersion.artifact_id == Artifact.id)
        .where(
            Artifact.workspace_id == auth.workspace_id,
            Artifact.project_id == project_id,
            Artifact.artifact_type == "research_memo",
        )
        .order_by(ArtifactVersion.created_at.desc())
    )


@lru_cache(maxsize=1)
def _research_eval_cases() -> list[ResearchEvalCaseRead]:
    path = Path(__file__).resolve().parent.parent / "evals" / "research_sprint_cases.json"
    raw_cases = json.loads(path.read_text(encoding="utf-8"))
    return [ResearchEvalCaseRead.model_validate(raw_case) for raw_case in raw_cases]


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


REQUIRED_RESEARCH_MEMO_SECTIONS = (
    "Executive Verdict",
    "Best Wedge",
    "Market Landscape",
    "Competitor Landscape",
    "Riskiest Assumptions",
    "Recommended Validation Actions",
    "Decision Recommendation",
    "Unsupported Claims / Open Questions",
)


def _contains_research_memo_sections(markdown: str) -> bool:
    return all(
        section.casefold() in markdown.casefold()
        for section in REQUIRED_RESEARCH_MEMO_SECTIONS
    )


def _research_memo_section_coverage(markdown: str) -> str:
    covered = sum(
        1
        for section in REQUIRED_RESEARCH_MEMO_SECTIONS
        if section.casefold() in markdown.casefold()
    )
    return f"{covered}/{len(REQUIRED_RESEARCH_MEMO_SECTIONS)}"


def _diagnostic_items(value: Any) -> list[dict[str, Any]]:
    if isinstance(value, list):
        return [item for item in value if isinstance(item, dict)]
    return []


def _has_multi_stage_retrieval(value: Any) -> bool:
    for item in _diagnostic_items(value):
        plan = item.get("query_plan")
        if isinstance(plan, dict) and (
            plan.get("decomposed") is True or len(plan.get("subqueries") or []) > 1
        ):
            return True
    return False


def _retrieval_strategy_observed(value: Any) -> str:
    items = _diagnostic_items(value)
    subquery_count = sum(
        len(item.get("query_plan", {}).get("subqueries") or [])
        for item in items
        if isinstance(item.get("query_plan"), dict)
    )
    return f"{len(items)} diagnostics, {subquery_count} subqueries"


def _has_reranker_diagnostics(value: Any) -> bool:
    return any(isinstance(item.get("reranker"), dict) for item in _diagnostic_items(value))


def _reranker_observed(value: Any) -> str:
    rerankers = [
        item.get("reranker")
        for item in _diagnostic_items(value)
        if isinstance(item.get("reranker"), dict)
    ]
    if not rerankers:
        return "no reranker diagnostics"
    enabled_count = sum(1 for reranker in rerankers if reranker.get("enabled") is True)
    providers = sorted({str(reranker.get("provider")) for reranker in rerankers})
    return f"{enabled_count}/{len(rerankers)} enabled, providers: {', '.join(providers)}"


def _has_context_assembly(context: Any, diagnostics: Any) -> bool:
    if isinstance(context, dict) and context.get("selected_count", 0) >= 1:
        return True
    return any(
        isinstance(item.get("context"), dict) and item["context"].get("selected_count", 0) >= 1
        for item in _diagnostic_items(diagnostics)
    )


def _context_assembly_observed(context: Any, diagnostics: Any) -> str:
    if isinstance(context, dict) and context:
        return (
            f"{context.get('selected_count', 0)} selected, "
            f"{context.get('token_count', 0)}/{context.get('token_budget', 0)} tokens"
        )
    contexts = [
        item.get("context")
        for item in _diagnostic_items(diagnostics)
        if isinstance(item.get("context"), dict)
    ]
    selected = sum(int(item.get("selected_count") or 0) for item in contexts)
    tokens = sum(int(item.get("token_count") or 0) for item in contexts)
    return f"{selected} selected, {tokens} tokens"


def _has_quality_report(value: Any) -> bool:
    return any(isinstance(item.get("quality_report"), dict) for item in _diagnostic_items(value))


def _quality_report_observed(value: Any) -> str:
    reports = [
        item.get("quality_report")
        for item in _diagnostic_items(value)
        if isinstance(item.get("quality_report"), dict)
    ]
    if not reports:
        return "no retrieval quality reports"
    avg_precision = sum(float(report.get("precision_proxy") or 0) for report in reports) / len(
        reports
    )
    avg_recall = sum(float(report.get("recall_proxy") or 0) for report in reports) / len(reports)
    return f"{len(reports)} reports, precision {avg_precision:.2f}, recall {avg_recall:.2f}"


def _secret_redaction_check() -> bool:
    sanitized = langsmith_observability_service.sanitize_for_observability(
        {
            "LANGSMITH_API_KEY": "lsv2-secret",
            "nested": {"authorization": "Bearer secret-token", "safe": "visible"},
        }
    )
    return (
        sanitized["LANGSMITH_API_KEY"] == "[redacted]"
        and sanitized["nested"]["authorization"] == "[redacted]"
        and sanitized["nested"]["safe"] == "visible"
    )
