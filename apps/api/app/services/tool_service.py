import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any, Literal

from fastapi import HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.auth import AuthContext
from app.core.config import Settings
from app.db.models import (
    Artifact,
    ArtifactVersion,
    Assumption,
    Competitor,
    CompetitorCandidate,
    Decision,
    EvidenceSource,
    Experiment,
    ResearchSprint,
    Risk,
    ToolInvocation,
)
from app.schemas.evidence import EvidenceRetrieveCreate
from app.services import project_service, retrieval_service

ToolAccessMode = Literal["read", "write", "proposal"]
ToolRiskLevel = Literal["low", "medium", "high"]
ApprovalPolicy = Literal["never_required", "required_for_write", "always_required"]
RequestedBy = Literal["agent", "user", "system"]


@dataclass(frozen=True)
class ToolDefinition:
    name: str
    title: str
    description: str
    input_schema: dict[str, Any]
    output_schema: dict[str, Any]
    access_mode: ToolAccessMode
    risk_level: ToolRiskLevel
    approval_policy: ApprovalPolicy
    allowed_project_roles: list[str]


@dataclass(frozen=True)
class ToolExecutionResult:
    invocation: ToolInvocation
    output: dict[str, Any]


PROJECT_ROLES = ["owner", "admin", "member"]


TOOL_REGISTRY: dict[str, ToolDefinition] = {
    "get_project_summary": ToolDefinition(
        name="get_project_summary",
        title="Get project summary",
        description="Read the structured thesis, customer segments, and problem hypotheses.",
        input_schema={"type": "object", "properties": {}, "additionalProperties": False},
        output_schema={"type": "object", "properties": {"project": {"type": "object"}}},
        access_mode="read",
        risk_level="low",
        approval_policy="never_required",
        allowed_project_roles=PROJECT_ROLES,
    ),
    "search_project_evidence": ToolDefinition(
        name="search_project_evidence",
        title="Search project evidence",
        description="Run scoped retrieval against project evidence chunks.",
        input_schema={
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "mode": {"type": "string", "enum": ["semantic", "keyword", "hybrid"]},
                "top_k": {"type": "integer", "minimum": 1, "maximum": 20},
            },
            "required": ["query"],
        },
        output_schema={"type": "object", "properties": {"results": {"type": "array"}}},
        access_mode="read",
        risk_level="low",
        approval_policy="never_required",
        allowed_project_roles=PROJECT_ROLES,
    ),
    "list_project_sources": ToolDefinition(
        name="list_project_sources",
        title="List project sources",
        description="List evidence sources and research source candidates for the project.",
        input_schema={"type": "object", "properties": {}, "additionalProperties": True},
        output_schema={"type": "object", "properties": {"sources": {"type": "array"}}},
        access_mode="read",
        risk_level="low",
        approval_policy="never_required",
        allowed_project_roles=PROJECT_ROLES,
    ),
    "list_competitors": ToolDefinition(
        name="list_competitors",
        title="List competitors",
        description="List approved competitors and research competitor candidates.",
        input_schema={"type": "object", "properties": {}, "additionalProperties": True},
        output_schema={"type": "object", "properties": {"competitors": {"type": "array"}}},
        access_mode="read",
        risk_level="low",
        approval_policy="never_required",
        allowed_project_roles=PROJECT_ROLES,
    ),
    "list_assumptions": ToolDefinition(
        name="list_assumptions",
        title="List assumptions",
        description="List current assumptions and risks.",
        input_schema={"type": "object", "properties": {}, "additionalProperties": False},
        output_schema={
            "type": "object",
            "properties": {"assumptions": {"type": "array"}, "risks": {"type": "array"}},
        },
        access_mode="read",
        risk_level="low",
        approval_policy="never_required",
        allowed_project_roles=PROJECT_ROLES,
    ),
    "list_validation_plans": ToolDefinition(
        name="list_validation_plans",
        title="List validation plans",
        description="List project experiments and validation-plan artifacts.",
        input_schema={"type": "object", "properties": {}, "additionalProperties": False},
        output_schema={
            "type": "object",
            "properties": {"experiments": {"type": "array"}, "artifacts": {"type": "array"}},
        },
        access_mode="read",
        risk_level="low",
        approval_policy="never_required",
        allowed_project_roles=PROJECT_ROLES,
    ),
    "list_decisions": ToolDefinition(
        name="list_decisions",
        title="List decisions",
        description="List recorded project decisions.",
        input_schema={"type": "object", "properties": {}, "additionalProperties": False},
        output_schema={"type": "object", "properties": {"decisions": {"type": "array"}}},
        access_mode="read",
        risk_level="low",
        approval_policy="never_required",
        allowed_project_roles=PROJECT_ROLES,
    ),
    "get_research_memo": ToolDefinition(
        name="get_research_memo",
        title="Get research memo",
        description="Read the latest research memo or the memo for a research sprint.",
        input_schema={
            "type": "object",
            "properties": {"research_sprint_id": {"type": "string", "format": "uuid"}},
        },
        output_schema={"type": "object", "properties": {"memo": {"type": "object"}}},
        access_mode="read",
        risk_level="low",
        approval_policy="never_required",
        allowed_project_roles=PROJECT_ROLES,
    ),
    "propose_research_plan": ToolDefinition(
        name="propose_research_plan",
        title="Propose research plan",
        description="Create an auditable proposed research plan before user approval.",
        input_schema={"type": "object", "properties": {"objective": {"type": "string"}}},
        output_schema={"type": "object", "properties": {"proposal": {"type": "object"}}},
        access_mode="proposal",
        risk_level="medium",
        approval_policy="always_required",
        allowed_project_roles=PROJECT_ROLES,
    ),
    "propose_memory_update": ToolDefinition(
        name="propose_memory_update",
        title="Propose memory update",
        description="Propose assumption, risk, and recommendation updates without mutating state.",
        input_schema={
            "type": "object",
            "properties": {"research_sprint_id": {"type": "string", "format": "uuid"}},
        },
        output_schema={"type": "object", "properties": {"proposal": {"type": "object"}}},
        access_mode="proposal",
        risk_level="medium",
        approval_policy="always_required",
        allowed_project_roles=PROJECT_ROLES,
    ),
    "propose_validation_plan": ToolDefinition(
        name="propose_validation_plan",
        title="Propose validation plan",
        description="Propose validation actions or experiments for human review.",
        input_schema={"type": "object", "properties": {"actions": {"type": "array"}}},
        output_schema={"type": "object", "properties": {"proposal": {"type": "object"}}},
        access_mode="proposal",
        risk_level="medium",
        approval_policy="always_required",
        allowed_project_roles=PROJECT_ROLES,
    ),
    "propose_decision": ToolDefinition(
        name="propose_decision",
        title="Propose decision",
        description="Propose a decision record without writing it to the decision ledger.",
        input_schema={"type": "object", "properties": {"decision": {"type": "object"}}},
        output_schema={"type": "object", "properties": {"proposal": {"type": "object"}}},
        access_mode="proposal",
        risk_level="medium",
        approval_policy="always_required",
        allowed_project_roles=PROJECT_ROLES,
    ),
}


def list_tool_definitions() -> list[ToolDefinition]:
    return list(TOOL_REGISTRY.values())


def list_tool_invocations(
    db: Session,
    auth: AuthContext,
    project_id: uuid.UUID,
    *,
    research_sprint_id: uuid.UUID | None = None,
    limit: int = 50,
) -> list[ToolInvocation]:
    project_service.get_project(db, auth, project_id)
    stmt = select(ToolInvocation).where(
        ToolInvocation.workspace_id == auth.workspace_id,
        ToolInvocation.project_id == project_id,
    )
    if research_sprint_id is not None:
        stmt = stmt.where(ToolInvocation.research_sprint_id == research_sprint_id)
    return list(
        db.scalars(stmt.order_by(ToolInvocation.created_at.desc()).limit(min(limit, 100)))
    )


def execute_tool(
    db: Session,
    auth: AuthContext,
    settings: Settings,
    project_id: uuid.UUID,
    tool_name: str,
    tool_input: dict[str, Any] | None = None,
    *,
    research_sprint_id: uuid.UUID | None = None,
    requested_by: RequestedBy = "agent",
) -> ToolExecutionResult:
    definition = _definition(tool_name)
    clean_input = _redact_payload(tool_input or {})
    invocation = ToolInvocation(
        workspace_id=auth.workspace_id,
        project_id=project_id,
        research_sprint_id=research_sprint_id,
        tool_name=definition.name,
        access_mode=definition.access_mode,
        risk_level=definition.risk_level,
        input_json=clean_input,
        status="requested" if definition.access_mode == "proposal" else "executed",
        requested_by=requested_by,
        executed_at=None if definition.access_mode == "proposal" else datetime.now(UTC),
    )
    db.add(invocation)
    db.flush()
    try:
        output = _run_tool(
            db,
            auth,
            settings,
            project_id,
            definition,
            tool_input or {},
            research_sprint_id,
        )
    except Exception as exc:
        invocation.status = "failed"
        invocation.output_summary = str(exc)[:1000]
        invocation.executed_at = datetime.now(UTC)
        db.commit()
        raise
    invocation.output_json = _redact_payload(output)
    invocation.output_summary = _summarize_output(definition.name, output)
    if definition.access_mode != "proposal":
        invocation.status = "executed"
        invocation.executed_at = datetime.now(UTC)
    db.commit()
    db.refresh(invocation)
    return ToolExecutionResult(invocation=invocation, output=output)


def create_proposal(
    db: Session,
    auth: AuthContext,
    project_id: uuid.UUID,
    tool_name: str,
    proposal: dict[str, Any],
    *,
    research_sprint_id: uuid.UUID | None = None,
    requested_by: RequestedBy = "agent",
    input_json: dict[str, Any] | None = None,
) -> ToolInvocation:
    definition = _definition(tool_name)
    if definition.access_mode != "proposal":
        raise ValueError(f"{tool_name} is not a proposal tool.")
    invocation = ToolInvocation(
        workspace_id=auth.workspace_id,
        project_id=project_id,
        research_sprint_id=research_sprint_id,
        tool_name=definition.name,
        access_mode=definition.access_mode,
        risk_level=definition.risk_level,
        input_json=_redact_payload(input_json or {}),
        output_json=_redact_payload({"proposal": proposal}),
        output_summary=_summarize_output(definition.name, {"proposal": proposal}),
        status="requested",
        requested_by=requested_by,
    )
    db.add(invocation)
    db.commit()
    db.refresh(invocation)
    return invocation


def approve_tool_invocation(
    db: Session,
    auth: AuthContext,
    project_id: uuid.UUID,
    invocation_id: uuid.UUID,
) -> ToolInvocation:
    invocation = _get_invocation(db, auth, project_id, invocation_id)
    if invocation.access_mode == "read":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Read tool invocations do not require approval.",
        )
    if invocation.status not in {"requested", "executed"}:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Only pending tool proposals can be approved.",
        )
    invocation.status = "approved"
    invocation.approved_by_user_id = auth.user_id
    invocation.executed_at = invocation.executed_at or datetime.now(UTC)
    db.commit()
    db.refresh(invocation)
    return invocation


def reject_tool_invocation(
    db: Session,
    auth: AuthContext,
    project_id: uuid.UUID,
    invocation_id: uuid.UUID,
) -> ToolInvocation:
    invocation = _get_invocation(db, auth, project_id, invocation_id)
    if invocation.access_mode == "read":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Read tool invocations do not require rejection.",
        )
    if invocation.status not in {"requested", "executed"}:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Only pending tool proposals can be rejected.",
        )
    invocation.status = "rejected"
    invocation.executed_at = invocation.executed_at or datetime.now(UTC)
    db.commit()
    db.refresh(invocation)
    return invocation


def approve_pending_proposals_for_sprint(
    db: Session,
    auth: AuthContext,
    project_id: uuid.UUID,
    research_sprint_id: uuid.UUID,
    tool_names: set[str],
) -> list[ToolInvocation]:
    proposals = list(
        db.scalars(
            select(ToolInvocation).where(
                ToolInvocation.workspace_id == auth.workspace_id,
                ToolInvocation.project_id == project_id,
                ToolInvocation.research_sprint_id == research_sprint_id,
                ToolInvocation.tool_name.in_(tool_names),
                ToolInvocation.status == "requested",
                ToolInvocation.access_mode == "proposal",
            )
        )
    )
    now = datetime.now(UTC)
    for proposal in proposals:
        proposal.status = "approved"
        proposal.approved_by_user_id = auth.user_id
        proposal.executed_at = proposal.executed_at or now
    db.flush()
    return proposals


def reject_pending_proposals_for_sprint(
    db: Session,
    auth: AuthContext,
    project_id: uuid.UUID,
    research_sprint_id: uuid.UUID,
    tool_names: set[str],
) -> list[ToolInvocation]:
    proposals = list(
        db.scalars(
            select(ToolInvocation).where(
                ToolInvocation.workspace_id == auth.workspace_id,
                ToolInvocation.project_id == project_id,
                ToolInvocation.research_sprint_id == research_sprint_id,
                ToolInvocation.tool_name.in_(tool_names),
                ToolInvocation.status == "requested",
                ToolInvocation.access_mode == "proposal",
            )
        )
    )
    now = datetime.now(UTC)
    for proposal in proposals:
        proposal.status = "rejected"
        proposal.executed_at = proposal.executed_at or now
    db.flush()
    return proposals


def _run_tool(
    db: Session,
    auth: AuthContext,
    settings: Settings,
    project_id: uuid.UUID,
    definition: ToolDefinition,
    tool_input: dict[str, Any],
    research_sprint_id: uuid.UUID | None,
) -> dict[str, Any]:
    if definition.name == "get_project_summary":
        return _get_project_summary(db, auth, project_id)
    if definition.name == "search_project_evidence":
        payload = EvidenceRetrieveCreate(
            query=str(tool_input.get("query") or ""),
            mode=tool_input.get("mode") or "hybrid",
            top_k=int(tool_input.get("top_k") or 8),
        )
        results = retrieval_service.retrieve_evidence_results(
            db,
            auth,
            settings,
            project_id,
            payload,
        )
        return {"results": [result.model_dump(mode="json") for result in results]}
    if definition.name == "list_project_sources":
        return _list_project_sources(db, auth, project_id, research_sprint_id)
    if definition.name == "list_competitors":
        return _list_competitors(db, auth, project_id, research_sprint_id)
    if definition.name == "list_assumptions":
        return _list_assumptions(db, auth, project_id)
    if definition.name == "list_validation_plans":
        return _list_validation_plans(db, auth, project_id)
    if definition.name == "list_decisions":
        return _list_decisions(db, auth, project_id)
    if definition.name == "get_research_memo":
        return _get_research_memo(db, auth, project_id, tool_input, research_sprint_id)
    if definition.access_mode == "proposal":
        return {"proposal": tool_input, "requires_human_approval": True}
    raise ValueError(f"Unsupported tool: {definition.name}")


def _get_project_summary(db: Session, auth: AuthContext, project_id: uuid.UUID) -> dict[str, Any]:
    project = project_service.get_project(db, auth, project_id)
    thesis = project_service.current_thesis(project)
    return {
        "project": {
            "id": str(project.id),
            "name": project.name,
            "short_description": project.short_description,
            "current_thesis": thesis.thesis_text if thesis else None,
            "confidence_score": _decimal_to_float(project.confidence_score),
            "customer_segments": [segment.name for segment in project.customer_segments],
            "problem_hypotheses": [problem.description for problem in project.problems],
        }
    }


def _list_project_sources(
    db: Session,
    auth: AuthContext,
    project_id: uuid.UUID,
    research_sprint_id: uuid.UUID | None,
) -> dict[str, Any]:
    evidence_sources = list(
        db.scalars(
            select(EvidenceSource)
            .where(
                EvidenceSource.workspace_id == auth.workspace_id,
                EvidenceSource.project_id == project_id,
            )
            .order_by(EvidenceSource.created_at.desc())
            .limit(20)
        )
    )
    sprint_sources = []
    if research_sprint_id is not None:
        sprint = db.scalar(
            select(ResearchSprint).where(
                ResearchSprint.workspace_id == auth.workspace_id,
                ResearchSprint.project_id == project_id,
                ResearchSprint.id == research_sprint_id,
            )
        )
        if sprint is not None:
            sprint_sources = [
                {
                    "id": str(source.id),
                    "evidence_source_id": str(source.evidence_source_id)
                    if source.evidence_source_id
                    else None,
                    "title": source.title,
                    "url": source.url,
                    "source_type": source.source_type,
                    "status": source.status,
                    "associated_research_question": source.associated_research_question,
                }
                for source in sprint.discovered_sources
            ]
    return {
        "sources": [
            {
                "id": str(source.id),
                "title": source.title,
                "url": source.url,
                "source_type": source.source_type,
                "classification": source.classification,
                "ingestion_status": source.ingestion_status,
                "summary": source.summary,
            }
            for source in evidence_sources
        ],
        "research_sources": sprint_sources,
    }


def _list_competitors(
    db: Session,
    auth: AuthContext,
    project_id: uuid.UUID,
    research_sprint_id: uuid.UUID | None,
) -> dict[str, Any]:
    competitors = list(
        db.scalars(
            select(Competitor)
            .where(
                Competitor.workspace_id == auth.workspace_id,
                Competitor.project_id == project_id,
            )
            .order_by(Competitor.updated_at.desc())
            .limit(30)
        )
    )
    candidates = []
    if research_sprint_id is not None:
        candidates = list(
            db.scalars(
                select(CompetitorCandidate)
                .where(
                    CompetitorCandidate.workspace_id == auth.workspace_id,
                    CompetitorCandidate.project_id == project_id,
                    CompetitorCandidate.research_sprint_id == research_sprint_id,
                )
                .order_by(CompetitorCandidate.relevance_score.desc())
            )
        )
    return {
        "competitors": [
            {
                "id": str(competitor.id),
                "name": competitor.name,
                "category": competitor.category,
                "target_user": competitor.target_user,
                "positioning": competitor.positioning,
                "pricing_summary": competitor.pricing_summary,
                "threat_level": competitor.threat_level,
            }
            for competitor in competitors
        ],
        "competitor_candidates": [
            {
                "id": str(candidate.id),
                "name": candidate.name,
                "category": candidate.category,
                "status": candidate.status,
                "target_user": candidate.target_user,
                "positioning": candidate.positioning,
                "why_it_matters": candidate.why_it_matters,
                "threat_level": candidate.threat_level,
            }
            for candidate in candidates
        ],
    }


def _list_assumptions(db: Session, auth: AuthContext, project_id: uuid.UUID) -> dict[str, Any]:
    assumptions = list(
        db.scalars(
            select(Assumption)
            .where(
                Assumption.workspace_id == auth.workspace_id,
                Assumption.project_id == project_id,
            )
            .order_by(Assumption.kill_risk.desc(), Assumption.updated_at.desc())
            .limit(30)
        )
    )
    risks = list(
        db.scalars(
            select(Risk)
            .where(Risk.workspace_id == auth.workspace_id, Risk.project_id == project_id)
            .order_by(Risk.updated_at.desc())
            .limit(20)
        )
    )
    return {
        "assumptions": [
            {
                "id": str(assumption.id),
                "text": assumption.text,
                "importance": assumption.importance,
                "uncertainty": assumption.uncertainty,
                "kill_risk": assumption.kill_risk,
                "status": assumption.status,
                "confidence_score": _decimal_to_float(assumption.confidence_score),
            }
            for assumption in assumptions
        ],
        "risks": [
            {
                "id": str(risk.id),
                "text": risk.text,
                "severity": risk.severity,
                "likelihood": risk.likelihood,
                "status": risk.status,
            }
            for risk in risks
        ],
    }


def _list_validation_plans(db: Session, auth: AuthContext, project_id: uuid.UUID) -> dict[str, Any]:
    experiments = list(
        db.scalars(
            select(Experiment)
            .where(
                Experiment.workspace_id == auth.workspace_id,
                Experiment.project_id == project_id,
            )
            .order_by(Experiment.updated_at.desc())
            .limit(20)
        )
    )
    artifacts = list(
        db.scalars(
            select(Artifact)
            .where(
                Artifact.workspace_id == auth.workspace_id,
                Artifact.project_id == project_id,
                Artifact.artifact_type == "validation_plan",
            )
            .order_by(Artifact.updated_at.desc())
            .limit(10)
        )
    )
    return {
        "experiments": [
            {
                "id": str(experiment.id),
                "name": experiment.name,
                "method": experiment.method,
                "status": experiment.status,
                "success_criteria": experiment.success_criteria,
            }
            for experiment in experiments
        ],
        "artifacts": [
            {
                "id": str(artifact.id),
                "title": artifact.title,
                "current_version_id": str(artifact.current_version_id)
                if artifact.current_version_id
                else None,
            }
            for artifact in artifacts
        ],
    }


def _list_decisions(db: Session, auth: AuthContext, project_id: uuid.UUID) -> dict[str, Any]:
    decisions = list(
        db.scalars(
            select(Decision)
            .where(Decision.workspace_id == auth.workspace_id, Decision.project_id == project_id)
            .order_by(Decision.created_at.desc())
            .limit(20)
        )
    )
    return {
        "decisions": [
            {
                "id": str(decision.id),
                "decision_type": decision.decision_type,
                "title": decision.title,
                "rationale": decision.rationale,
                "review_date": decision.review_date.isoformat() if decision.review_date else None,
                "created_at": decision.created_at.isoformat(),
            }
            for decision in decisions
        ]
    }


def _get_research_memo(
    db: Session,
    auth: AuthContext,
    project_id: uuid.UUID,
    tool_input: dict[str, Any],
    research_sprint_id: uuid.UUID | None,
) -> dict[str, Any]:
    sprint_filter = tool_input.get("research_sprint_id") or (
        str(research_sprint_id) if research_sprint_id else None
    )
    versions = list(
        db.scalars(
            select(ArtifactVersion)
            .join(Artifact, Artifact.id == ArtifactVersion.artifact_id)
            .where(
                Artifact.workspace_id == auth.workspace_id,
                Artifact.project_id == project_id,
                Artifact.artifact_type == "research_memo",
            )
            .order_by(ArtifactVersion.created_at.desc())
            .limit(20)
        )
    )
    for version in versions:
        content = version.structured_content or {}
        if sprint_filter and content.get("research_sprint_id") != sprint_filter:
            continue
        return {
            "memo": {
                "artifact_version_id": str(version.id),
                "version": version.version,
                "research_sprint_id": content.get("research_sprint_id"),
                "memory_update_status": content.get("memory_update_status"),
                "summary": _truncate(version.markdown_content, 1200),
            }
        }
    return {"memo": None}


def _definition(tool_name: str) -> ToolDefinition:
    definition = TOOL_REGISTRY.get(tool_name)
    if definition is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tool not found.")
    return definition


def _get_invocation(
    db: Session,
    auth: AuthContext,
    project_id: uuid.UUID,
    invocation_id: uuid.UUID,
) -> ToolInvocation:
    invocation = db.scalar(
        select(ToolInvocation).where(
            ToolInvocation.id == invocation_id,
            ToolInvocation.workspace_id == auth.workspace_id,
            ToolInvocation.project_id == project_id,
        )
    )
    if invocation is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tool invocation not found.",
        )
    return invocation


def _summarize_output(tool_name: str, output: dict[str, Any]) -> str:
    if tool_name == "search_project_evidence":
        return f"Searched project evidence and returned {len(output.get('results', []))} result(s)."
    if tool_name == "list_project_sources":
        return (
            f"Listed {len(output.get('sources', []))} evidence source(s) and "
            f"{len(output.get('research_sources', []))} research source candidate(s)."
        )
    if tool_name == "list_competitors":
        return (
            f"Listed {len(output.get('competitors', []))} competitor(s) and "
            f"{len(output.get('competitor_candidates', []))} candidate(s)."
        )
    if tool_name == "list_assumptions":
        return (
            f"Listed {len(output.get('assumptions', []))} assumption(s) and "
            f"{len(output.get('risks', []))} risk(s)."
        )
    if tool_name.startswith("propose_"):
        proposal = output.get("proposal") or {}
        if isinstance(proposal, dict):
            return str(proposal.get("summary") or "Project update proposed.")[:1000]
        return "Project update proposed."
    if tool_name == "get_project_summary":
        project = output.get("project") or {}
        return f"Loaded project summary for {project.get('name', 'project')}."
    return f"Executed {tool_name}."


def _redact_payload(payload: Any) -> Any:
    if isinstance(payload, BaseModel):
        payload = payload.model_dump(mode="json")
    if isinstance(payload, dict):
        redacted: dict[str, Any] = {}
        for key, value in payload.items():
            lower = key.lower()
            if "secret" in lower or "token" in lower or "api_key" in lower or "password" in lower:
                redacted[key] = "[redacted]"
            else:
                redacted[key] = _redact_payload(value)
        return redacted
    if isinstance(payload, list):
        return [_redact_payload(item) for item in payload[:50]]
    if isinstance(payload, uuid.UUID):
        return str(payload)
    if isinstance(payload, Decimal):
        return float(payload)
    if isinstance(payload, datetime):
        return payload.isoformat()
    return payload


def _decimal_to_float(value: Decimal | None) -> float | None:
    return float(value) if value is not None else None


def _truncate(value: str | None, limit: int) -> str | None:
    if value is None:
        return None
    return value if len(value) <= limit else f"{value[:limit - 1]}..."
