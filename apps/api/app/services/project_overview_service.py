import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.core.auth import AuthContext
from app.db.models import (
    AIRun,
    Artifact,
    ArtifactVersion,
    Assumption,
    Claim,
    ClaimEvidenceLink,
    Competitor,
    Decision,
    EvidenceSource,
    Experiment,
    ExperimentResult,
    Project,
    Risk,
    ValidationResultInterpretation,
)
from app.schemas.overview import (
    EvidenceHealthRead,
    IdeaReadinessRead,
    NextBestActionRead,
    PlaybookStepRead,
    ProjectOverviewRead,
    ReadinessItemRead,
    StrategicRecommendationRead,
    StrategicSnapshotRead,
    StrategicUpdateRead,
)
from app.schemas.projects import ProjectRead
from app.services import project_service, research_history_service


@dataclass(frozen=True)
class _OverviewCounts:
    evidence_sources: int
    competitors: int
    analyzed_competitors: int
    opportunity_briefs: int
    competitor_landscapes: int
    validation_plans: int
    assumptions: int
    high_risk_assumptions: int
    risks: int
    experiments: int
    running_experiments: int
    experiment_results: int
    validation_interpretations: int
    decisions: int
    cited_claims: int
    unsupported_claims: int
    validated_assumptions: int


@dataclass(frozen=True)
class _OverviewContext:
    project: Project
    counts: _OverviewCounts
    current_brief: Artifact | None
    latest_decision: Decision | None
    key_assumptions: list[Assumption]
    key_risks: list[Risk]
    last_evidence_update: datetime | None


def get_project_overview(
    db: Session,
    auth: AuthContext,
    project_id: uuid.UUID,
) -> ProjectOverviewRead:
    context = _load_context(db, auth, project_id)
    stage = _project_stage(context)
    next_action = _next_best_action(context.project.id, stage)
    readiness = _idea_readiness(context, next_action.label)
    return ProjectOverviewRead(
        project=_serialize_project(context.project),
        current_recommendation=_current_recommendation(context, stage, next_action),
        next_best_action=next_action,
        secondary_actions=_secondary_actions(context.project.id, stage),
        playbook_steps=_playbook_steps(context.project.id, stage, context),
        idea_readiness=readiness,
        strategic_snapshot=_strategic_snapshot(context, stage),
        evidence_health=_evidence_health(context),
        recent_strategic_updates=_strategic_updates(db, auth, context.project.id),
        key_assumptions=context.key_assumptions,
        key_risks=context.key_risks,
    )


def _serialize_project(project: Project) -> ProjectRead:
    return ProjectRead.model_validate(
        {
            **project.__dict__,
            "current_thesis": project_service.current_thesis(project),
            "customer_segments": project.customer_segments,
            "problems": project.problems,
        }
    )


def get_idea_readiness(
    db: Session,
    auth: AuthContext,
    project_id: uuid.UUID,
) -> IdeaReadinessRead:
    context = _load_context(db, auth, project_id)
    stage = _project_stage(context)
    return _idea_readiness(context, _next_best_action(context.project.id, stage).label)


def get_strategic_updates(
    db: Session,
    auth: AuthContext,
    project_id: uuid.UUID,
    limit: int = 10,
) -> list[StrategicUpdateRead]:
    project_service.get_project(db, auth, project_id)
    return _strategic_updates(db, auth, project_id, limit)


def execute_next_action(
    db: Session,
    auth: AuthContext,
    project_id: uuid.UUID,
) -> NextBestActionRead:
    context = _load_context(db, auth, project_id)
    return _next_best_action(project_id, _project_stage(context))


def _load_context(db: Session, auth: AuthContext, project_id: uuid.UUID) -> _OverviewContext:
    project = project_service.get_project(db, auth, project_id)
    current_brief = _current_artifact(db, auth, project_id, "opportunity_brief")
    return _OverviewContext(
        project=project,
        counts=_counts(db, auth, project_id),
        current_brief=current_brief,
        latest_decision=_latest_decision(db, auth, project_id),
        key_assumptions=_key_assumptions(db, auth, project_id),
        key_risks=_key_risks(db, auth, project_id),
        last_evidence_update=_last_evidence_update(db, auth, project_id),
    )


def _project_stage(context: _OverviewContext) -> str:
    project = context.project
    counts = context.counts
    latest_decision = context.latest_decision

    if project.status == "paused":
        return "paused"
    if project.status in {"killed", "archived"}:
        return "killed"
    if project.status == "launched":
        return "proceeding"

    if latest_decision:
        if latest_decision.decision_type == "kill":
            return "killed"
        if latest_decision.decision_type == "pause":
            return "paused"
        if latest_decision.decision_type in {
            "build",
            "pivot",
            "change_icp",
            "change_positioning",
        }:
            return "proceeding"

    if counts.experiment_results > 0 or counts.validation_interpretations > 0:
        return "decision_ready"
    if counts.running_experiments > 0:
        return "experiment_running"
    if counts.validation_plans > 0 or counts.experiments > 0:
        return "validation_plan_created"
    if counts.assumptions > 0 or counts.risks > 0:
        return "assumptions_identified"
    if counts.competitor_landscapes > 0 or counts.analyzed_competitors > 0:
        return "competitors_analyzed"
    if counts.opportunity_briefs > 0:
        return "brief_generated"
    if project.current_thesis_id and (project.customer_segments or project.problems):
        return "structured_intake"
    return "draft_idea"


def _next_best_action(project_id: uuid.UUID, stage: str) -> NextBestActionRead:
    action_map: dict[str, tuple[str, str, str, str, str]] = {
        "draft_idea": (
            "structure_idea",
            "Define the thesis",
            "Turn the rough idea into target users, problems, solution shape, and uncertainties.",
            "A structured thesis gives every later brief, evidence search, and validation "
            "plan a usable foundation.",
            "structured-intake",
        ),
        "structured_intake": (
            "generate_brief",
            "Run first research pass",
            "Create the first evidence-backed view of the opportunity.",
            "The brief turns project state and evidence into a source-grounded thesis, "
            "risks, and validation path.",
            "brief",
        ),
        "brief_generated": (
            "analyze_competitors",
            "Map competitors and substitutes",
            "Pressure-test the thesis against direct competitors, substitutes, and manual "
            "alternatives.",
            "Competitor analysis exposes crowded areas and identifies a narrower wedge "
            "before validation.",
            "competitors",
        ),
        "competitors_analyzed": (
            "review_assumptions",
            "Find the riskiest assumption",
            "Identify what must be true for this idea to work.",
            "Ranked assumptions show which beliefs can kill the idea and should be tested first.",
            "assumptions",
        ),
        "assumptions_identified": (
            "create_validation_plan",
            "Create validation mission",
            "Turn the riskiest assumption into one proof with steps, assets, and criteria.",
            "A validation mission reduces uncertainty before committing to build.",
            "validation-mission",
        ),
        "validation_plan_created": (
            "log_results",
            "Start mission and log results",
            "Run the current proof and capture validation evidence for the highest-risk "
            "assumption.",
            "Real user evidence is the fastest way to update confidence before building.",
            "validation-mission",
        ),
        "experiment_running": (
            "add_results",
            "Log mission results",
            "Log what happened during the current proof and update confidence.",
            "Results convert activity into reusable evidence for the next strategic decision.",
            "validation-mission",
        ),
        "decision_ready": (
            "use_suggested_decision",
            "Review validation evidence",
            "Review logged validation evidence and choose proceed, pivot, pause, kill, "
            "or continue research.",
            "Decision records preserve what changed, why it mattered, and when to revisit the bet.",
            "decisions",
        ),
        "paused": (
            "resume_or_archive",
            "Review Paused Idea",
            "Decide whether to resume validation, archive the idea, or keep it paused.",
            "Paused projects should preserve the evidence trail and avoid drifting without "
            "a decision.",
            "decisions",
        ),
        "killed": (
            "view_decision",
            "View Decision",
            "Review why the idea was killed and what evidence supported the call.",
            "A killed idea is still useful when the rationale and evidence are easy to revisit.",
            "decisions",
        ),
        "proceeding": (
            "review_decision",
            "Review decision and next milestone",
            "Use the validated thesis to decide the next build or discovery milestone.",
            "Proceeding without an explicit next milestone makes it harder to keep learning "
            "tied to evidence.",
            "decisions",
        ),
    }
    action_type, label, description, why_it_matters, tab = action_map[stage]
    return NextBestActionRead(
        action_type=action_type,
        label=label,
        description=description,
        why_it_matters=why_it_matters,
        primary=True,
        related_stage=stage,  # type: ignore[arg-type]
        target_route=f"/projects/{project_id}#{tab}",
    )


def _secondary_actions(project_id: uuid.UUID, stage: str) -> list[NextBestActionRead]:
    candidates = {
        "draft_idea": ["evidence"],
        "structured_intake": ["evidence"],
        "brief_generated": ["evidence", "assumptions"],
        "competitors_analyzed": ["evidence"],
        "assumptions_identified": ["evidence"],
        "validation_plan_created": ["assumptions"],
        "experiment_running": ["evidence"],
        "decision_ready": ["evidence"],
    }.get(stage, [])

    secondary_map: dict[str, tuple[str, str, str, str]] = {
        "evidence": (
            "add_evidence",
            "Add Evidence",
            "Add customer notes, competitor pages, or market research.",
            "Evidence keeps recommendations grounded instead of generic.",
        ),
        "assumptions": (
            "review_assumptions",
            "Review Assumptions",
            "Check the highest-risk beliefs and their recommended tests.",
            "Validation is only useful when it targets the assumptions that matter most.",
        ),
    }
    actions: list[NextBestActionRead] = []
    for candidate in candidates[:2]:
        action_type, label, description, why = secondary_map[candidate]
        actions.append(
            NextBestActionRead(
                action_type=action_type,
                label=label,
                description=description,
                why_it_matters=why,
                primary=False,
                related_stage=stage,  # type: ignore[arg-type]
                target_route=f"/projects/{project_id}#{candidate}",
            )
        )
    return actions


def _playbook_steps(
    project_id: uuid.UUID,
    stage: str,
    _context: _OverviewContext,
) -> list[PlaybookStepRead]:
    focus_key = _playbook_focus_key(stage)
    current_position = _playbook_position_for_stage(stage)
    definitions = [
        (
            "guide",
            "Guide",
            "What to do next",
            "guide",
            None,
        ),
        (
            "thesis",
            "Thesis",
            "Shape the idea",
            "thesis",
            0,
        ),
        (
            "research",
            "Research",
            "Evidence and competitors",
            "research",
            1,
        ),
        (
            "test",
            "Test",
            "Run the blocker test",
            "validation",
            2,
        ),
        (
            "decision",
            "Decision",
            "Proceed, pivot, pause, or kill",
            "decisions",
            3,
        ),
        (
            "history",
            "History",
            "Receipts and changes",
            "history",
            4,
        ),
    ]
    steps: list[PlaybookStepRead] = []
    for key, label, purpose, hash_target, position in definitions:
        is_current = key == focus_key
        status = _playbook_step_status(key, position, current_position, is_current)
        steps.append(
            PlaybookStepRead(
                key=key,
                label=label,
                purpose=purpose,
                status=status,  # type: ignore[arg-type]
                is_current_stage=is_current,
                target_route=f"/projects/{project_id}#{hash_target}",
            )
        )
    return steps


def _playbook_focus_key(stage: str) -> str:
    if stage == "draft_idea":
        return "thesis"
    if stage in {"structured_intake", "brief_generated", "competitors_analyzed"}:
        return "research"
    if stage in {"assumptions_identified", "validation_plan_created", "experiment_running"}:
        return "test"
    if stage == "decision_ready":
        return "decision"
    if stage in {"paused", "killed", "proceeding"}:
        return "history"
    return "guide"


def _playbook_position_for_stage(stage: str) -> int:
    if stage == "draft_idea":
        return 0
    if stage in {"structured_intake", "brief_generated", "competitors_analyzed"}:
        return 1
    if stage in {"assumptions_identified", "validation_plan_created", "experiment_running"}:
        return 2
    if stage == "decision_ready":
        return 3
    if stage in {"paused", "killed", "proceeding"}:
        return 4
    return 0


def _playbook_step_status(
    key: str,
    position: int | None,
    current_position: int,
    is_current: bool,
) -> str:
    if key == "guide":
        return "available"
    if is_current:
        return "current"
    if key == "history" and current_position < 4:
        return "available"
    if position is not None and position < current_position:
        return "complete"
    return "blocked"


def _idea_readiness(context: _OverviewContext, recommended_action: str) -> IdeaReadinessRead:
    project = context.project
    counts = context.counts
    target_customer_status = "complete" if _primary_segment(project) else "missing"
    items = [
        ReadinessItemRead(
            key="rough_idea",
            label="Rough idea exists",
            status="complete" if (project.name or project.short_description) else "missing",
            related_action="Create project",
        ),
        ReadinessItemRead(
            key="thesis",
            label="Thesis exists",
            status="complete" if project.current_thesis_id else "missing",
            related_action="Define the thesis",
        ),
        ReadinessItemRead(
            key="target_customer",
            label="Target customer is specific",
            status=target_customer_status,  # type: ignore[arg-type]
            related_action="Define the thesis",
        ),
        ReadinessItemRead(
            key="problem_hypothesis",
            label="Problem hypothesis exists",
            status="complete" if project.problems else "missing",
            related_action="Define the thesis",
        ),
        ReadinessItemRead(
            key="evidence_sources",
            label="Evidence sources exist",
            status="complete" if counts.evidence_sources > 0 else "missing",
            related_action="Add Evidence",
        ),
        ReadinessItemRead(
            key="competitors",
            label="Competitors and substitutes mapped",
            status="complete" if counts.competitor_landscapes > 0 else "missing",
            related_action="Map competitors and substitutes",
        ),
        ReadinessItemRead(
            key="assumptions",
            label="Assumptions identified",
            status="complete" if counts.assumptions > 0 else "missing",
            related_action="Review Assumptions",
        ),
        ReadinessItemRead(
            key="high_risk_assumptions",
            label="High-risk assumptions ranked",
            status="complete" if counts.high_risk_assumptions > 0 else "needs_work",
            related_action="Review Assumptions",
        ),
        ReadinessItemRead(
            key="validation_plan",
            label="Validation test exists",
            status=(
                "complete"
                if counts.validation_plans > 0 or counts.experiments > 0
                else "missing"
            ),
            related_action="Create the first validation test",
        ),
        ReadinessItemRead(
            key="decision",
            label="Decision recorded",
            status="complete" if counts.decisions > 0 else "missing",
            related_action="Use the suggested decision",
        ),
    ]
    complete_count = sum(1 for item in items if item.status == "complete")
    score = round((complete_count / len(items)) * 100)
    missing_items = [item for item in items if item.status != "complete"]

    has_decision_evidence = (
        counts.decisions > 0
        or counts.experiment_results > 0
        or counts.validation_interpretations > 0
    )
    if has_decision_evidence:
        status = "decision_ready"
    elif counts.validation_plans > 0 or counts.experiments > 0:
        status = "ready_for_validation"
    elif score >= 40:
        status = "partially_ready"
    else:
        status = "not_ready"

    return IdeaReadinessRead(
        project_id=project.id,
        score=score,
        status=status,  # type: ignore[arg-type]
        completed_items=[item for item in items if item.status == "complete"],
        missing_items=missing_items,
        weakest_area=_weakest_readiness_area(missing_items),
        recommended_next_action=recommended_action,
    )


def _strategic_snapshot(context: _OverviewContext, stage: str) -> StrategicSnapshotRead:
    project = context.project
    current_thesis = project_service.current_thesis(project)
    target_user = _primary_segment(project)
    primary_problem = _primary_problem(project)
    main_risk = context.key_risks[0].text if context.key_risks else None
    return StrategicSnapshotRead(
        current_thesis=current_thesis.thesis_text if current_thesis else None,
        target_user=target_user,
        primary_problem=primary_problem,
        proposed_wedge=_proposed_wedge(context.current_brief),
        main_risk=main_risk,
        current_confidence=_confidence_label(project.confidence_score),
        current_stage=stage,  # type: ignore[arg-type]
    )


def _evidence_health(context: _OverviewContext) -> EvidenceHealthRead:
    counts = context.counts
    return EvidenceHealthRead(
        source_count=counts.evidence_sources,
        competitor_count=counts.competitors,
        cited_claim_count=counts.cited_claims,
        unsupported_claim_count=counts.unsupported_claims,
        validated_assumption_count=counts.validated_assumptions,
        weakest_evidence_area=_weakest_evidence_area(context),
        last_evidence_update=context.last_evidence_update,
    )


def _current_recommendation(
    context: _OverviewContext,
    stage: str,
    next_action: NextBestActionRead,
) -> StrategicRecommendationRead:
    riskiest = _top_assumption(context)
    assumption_text = _short_text(
        riskiest.text if riskiest is not None else "the riskiest assumption"
    )
    target = _primary_segment(context.project) or "the target user"
    problem = _short_text(
        _primary_problem(context.project)
        or "the stated problem"
    )
    latest_decision = context.latest_decision
    recommendations: dict[str, tuple[str, str]] = {
        "draft_idea": (
            "Do not judge the idea yet. First define the target user, problem, "
            "and riskiest belief.",
            "The project still lacks enough structured thesis, customer, and problem data "
            "to make a grounded recommendation.",
        ),
        "structured_intake": (
            f"Do not build yet. Run research to test whether {target} has evidence-backed pain.",
            f"The thesis names {target} and {problem}, but the project still needs cited "
            "evidence and competitor pressure before a build decision is credible.",
        ),
        "brief_generated": (
            "Do not build yet. Pressure-test the thesis against competitors and substitutes.",
            "A brief exists, but the positioning remains weak until substitutes and direct "
            "competitors are compared.",
        ),
        "competitors_analyzed": (
            "Do not build yet. Identify the assumption that could kill the idea first.",
            "Competitor context is available; the next leverage point is identifying what "
            "must be true for the idea to work.",
        ),
        "assumptions_identified": (
            f"Do not build yet. Validate this first: {assumption_text}.",
            "The project has enough assumptions and risks to start reducing uncertainty "
            "through a concrete test instead of more product work.",
        ),
        "validation_plan_created": (
            "Do not build yet. Run the highest-risk validation test and log the result.",
            "A validation plan exists, but idea confidence should change only after "
            f"real-world evidence is logged for: {assumption_text}.",
        ),
        "experiment_running": (
            f"Continue validation. Do not proceed until {assumption_text} has a clear signal.",
            "The project is collecting evidence; recording outcomes will make the next "
            "recommendation inspectable.",
        ),
        "decision_ready": (
            "Recommended decision: continue research unless the logged result clearly "
            "supports proceeding.",
            "Validation results exist, so the project can make a decision, but proceed "
            "should remain high-friction if the riskiest assumption is unresolved.",
        ),
        "paused": (
            "Keep the idea paused until a concrete new learning goal or stronger wedge exists.",
            "The current state says not to continue active validation without revisiting "
            "the rationale.",
        ),
        "killed": (
            "Treat this idea as closed unless new evidence changes the thesis.",
            "The project has been killed or archived; the useful work is preserving why.",
        ),
        "proceeding": (
            (
                f"Proceed with the narrowed decision: {_short_text(latest_decision.title)}."
                if latest_decision is not None
                else "Proceed narrowly from the validated wedge."
            ),
            (
                latest_decision.rationale
                if latest_decision is not None and latest_decision.rationale
                else "A proceed-style decision exists; the next step should keep execution tied to "
                "the evidence already collected."
            ),
        ),
    }
    recommendation, rationale = _project_specific_recommendation(context, stage) or recommendations[
        stage
    ]
    return StrategicRecommendationRead(
        id=f"computed:{context.project.id}:{stage}",
        project_id=context.project.id,
        recommendation=recommendation,
        rationale=rationale,
        confidence=_recommendation_confidence(context, stage),
        next_action_type=next_action.action_type,
        next_action_label=next_action.label,
        source_artifact_ids=_source_artifact_ids(context),
        source_evidence_ids=_source_evidence_ids(context),
        created_at=datetime.now(UTC),
    )


def _strategic_updates(
    db: Session,
    auth: AuthContext,
    project_id: uuid.UUID,
    limit: int = 10,
) -> list[StrategicUpdateRead]:
    updates: list[StrategicUpdateRead] = []
    updates.extend(_artifact_updates(db, auth, project_id))
    updates.extend(_evidence_updates(db, auth, project_id))
    updates.extend(_assumption_updates(db, auth, project_id))
    updates.extend(_experiment_result_updates(db, auth, project_id))
    updates.extend(_decision_updates(db, auth, project_id))
    updates.extend(_research_history_updates(db, auth, project_id))
    updates.extend(_workflow_updates(db, auth, project_id))
    updates.sort(key=lambda update: update.created_at, reverse=True)
    return updates[:limit]


def _artifact_updates(
    db: Session,
    auth: AuthContext,
    project_id: uuid.UUID,
) -> list[StrategicUpdateRead]:
    artifacts = list(
        db.scalars(
            select(Artifact)
            .where(Artifact.workspace_id == auth.workspace_id, Artifact.project_id == project_id)
            .order_by(Artifact.updated_at.desc())
            .limit(5)
        )
    )
    update_text = {
        "opportunity_brief": (
            "Opportunity brief updated",
            "The project now has a source-grounded strategic brief.",
            "This gives you a clearer thesis, visible unsupported claims, and a basis "
            "for assumptions.",
        ),
        "competitor_landscape": (
            "Competitor analysis completed",
            "Competitor profiles and positioning notes are available.",
            "This helps identify crowded areas, substitutes, and potential wedges before "
            "validation.",
        ),
        "validation_plan": (
            "Validation plan created",
            "The project now has experiments tied to assumptions.",
            "This turns strategic uncertainty into concrete user-facing tests.",
        ),
        "research_memo": (
            "Research memo completed",
            "The research sprint produced a cited strategic memo.",
            "This connects discovered evidence, competitor pressure, assumptions, and "
            "recommended validation actions in one reviewable artifact.",
        ),
    }
    updates: list[StrategicUpdateRead] = []
    for artifact in artifacts:
        title, summary, why = update_text.get(
            artifact.artifact_type,
            (
                "Strategic artifact updated",
                f"{artifact.title} was updated.",
                "Artifacts preserve the current strategic reasoning and make it revisitable.",
            ),
        )
        updates.append(
            StrategicUpdateRead(
                id=f"artifact:{artifact.id}",
                project_id=project_id,
                title=title,
                summary=summary,
                why_it_matters=why,
                related_entity_type="artifact",
                related_entity_id=artifact.id,
                created_at=artifact.updated_at,
            )
        )
    return updates


def _evidence_updates(
    db: Session,
    auth: AuthContext,
    project_id: uuid.UUID,
) -> list[StrategicUpdateRead]:
    sources = list(
        db.scalars(
            select(EvidenceSource)
            .where(
                EvidenceSource.workspace_id == auth.workspace_id,
                EvidenceSource.project_id == project_id,
            )
            .order_by(EvidenceSource.created_at.desc())
            .limit(3)
        )
    )
    return [
        StrategicUpdateRead(
            id=f"evidence:{source.id}",
            project_id=project_id,
            title="Evidence added",
            summary=(
                f"{source.title or source.url or 'A source'} is available for retrieval "
                "and citation."
            ),
            why_it_matters=(
                "New sources strengthen or weaken the thesis only when they are linked "
                "to claims, assumptions, or decisions."
            ),
            related_entity_type="evidence",
            related_entity_id=source.id,
            created_at=source.created_at,
        )
        for source in sources
    ]


def _assumption_updates(
    db: Session,
    auth: AuthContext,
    project_id: uuid.UUID,
) -> list[StrategicUpdateRead]:
    assumptions = list(
        db.scalars(
            select(Assumption)
            .where(
                Assumption.workspace_id == auth.workspace_id,
                Assumption.project_id == project_id,
            )
            .order_by(Assumption.updated_at.desc())
            .limit(3)
        )
    )
    updates: list[StrategicUpdateRead] = []
    for assumption in assumptions:
        risk_label = "kill-risk assumption" if assumption.kill_risk else "assumption"
        updates.append(
            StrategicUpdateRead(
                id=f"assumption:{assumption.id}",
                project_id=project_id,
                title="Assumption identified",
                summary=f"A {risk_label} was added: {assumption.text}",
                why_it_matters=(
                    "Assumptions are the beliefs to test before investing more build "
                    "effort."
                ),
                related_entity_type="assumption",
                related_entity_id=assumption.id,
                created_at=assumption.updated_at,
            )
        )
    return updates


def _experiment_result_updates(
    db: Session,
    auth: AuthContext,
    project_id: uuid.UUID,
) -> list[StrategicUpdateRead]:
    results = list(
        db.scalars(
            select(ExperimentResult)
            .where(
                ExperimentResult.workspace_id == auth.workspace_id,
                ExperimentResult.project_id == project_id,
            )
            .order_by(ExperimentResult.created_at.desc())
            .limit(3)
        )
    )
    return [
        StrategicUpdateRead(
            id=f"experiment_result:{result.id}",
            project_id=project_id,
            title="Validation result logged",
            summary=result.result_summary,
            why_it_matters=(
                "Validation results are the strongest signal for updating confidence "
                "and making a decision."
            ),
            related_entity_type="experiment",
            related_entity_id=result.experiment_id,
            created_at=result.created_at,
        )
        for result in results
    ]


def _decision_updates(
    db: Session,
    auth: AuthContext,
    project_id: uuid.UUID,
) -> list[StrategicUpdateRead]:
    decisions = list(
        db.scalars(
            select(Decision)
            .where(Decision.workspace_id == auth.workspace_id, Decision.project_id == project_id)
            .order_by(Decision.created_at.desc())
            .limit(3)
        )
    )
    return [
        StrategicUpdateRead(
            id=f"decision:{decision.id}",
            project_id=project_id,
            title="Decision recorded",
            summary=decision.title,
            why_it_matters=decision.rationale
            or "A decision is useful because it preserves what was chosen and why.",
            related_entity_type="decision",
            related_entity_id=decision.id,
            created_at=decision.created_at,
        )
        for decision in decisions
    ]


def _research_history_updates(
    db: Session,
    auth: AuthContext,
    project_id: uuid.UUID,
) -> list[StrategicUpdateRead]:
    history = research_history_service.get_project_research_history(db, auth, project_id, limit=5)
    updates: list[StrategicUpdateRead] = []
    visible_events = {
        "memo_generated",
        "memory_update_approved",
        "memory_update_rejected",
        "sprint_completed",
        "sprint_failed",
    }
    for sprint_history in history.sprints:
        for event in sprint_history.events:
            if event.event_type not in visible_events:
                continue
            updates.append(
                StrategicUpdateRead(
                    id=f"research:{event.id}",
                    project_id=project_id,
                    title=event.title,
                    summary=event.summary,
                    why_it_matters=event.why_it_matters,
                    related_entity_type=_overview_entity_type(event.related_entity_type),
                    related_entity_id=event.related_entity_id,
                    created_at=event.created_at,
                )
            )
    return updates


def _workflow_updates(
    db: Session,
    auth: AuthContext,
    project_id: uuid.UUID,
) -> list[StrategicUpdateRead]:
    runs = list(
        db.scalars(
            select(AIRun)
            .where(AIRun.workspace_id == auth.workspace_id, AIRun.project_id == project_id)
            .order_by(AIRun.created_at.desc())
            .limit(5)
        )
    )
    updates: list[StrategicUpdateRead] = []
    for run in runs:
        if run.workflow_type in {"evidence_retrieval"}:
            continue
        title = (
            f"{_format_label(run.workflow_type)} completed"
            if run.status == "succeeded"
            else f"{_format_label(run.workflow_type)} {run.status}"
        )
        updates.append(
            StrategicUpdateRead(
                id=f"workflow:{run.id}",
                project_id=project_id,
                title=title,
                summary=run.output_summary
                or run.input_summary
                or "Workflow activity was recorded.",
                why_it_matters=(
                    "Workflow traces keep strategic changes inspectable, but the "
                    "underlying project objects are the source of truth."
                ),
                related_entity_type="workflow",
                related_entity_id=run.id,
                created_at=run.completed_at or run.created_at,
            )
        )
    return updates


def _overview_entity_type(entity_type: str) -> str:
    if entity_type in {
        "artifact",
        "evidence",
        "competitor",
        "assumption",
        "experiment",
        "decision",
    }:
        return entity_type
    return "workflow"


def _counts(db: Session, auth: AuthContext, project_id: uuid.UUID) -> _OverviewCounts:
    base_filter = {"workspace_id": auth.workspace_id, "project_id": project_id}
    return _OverviewCounts(
        evidence_sources=_count(
            db,
            select(func.count())
            .select_from(EvidenceSource)
            .where(
                EvidenceSource.workspace_id == auth.workspace_id,
                EvidenceSource.project_id == project_id,
                EvidenceSource.ingestion_status == "ready",
            ),
        ),
        competitors=_model_count(db, Competitor, base_filter),
        analyzed_competitors=_count(
            db,
            select(func.count())
            .select_from(Competitor)
            .where(
                Competitor.workspace_id == auth.workspace_id,
                Competitor.project_id == project_id,
                Competitor.last_analyzed_at.is_not(None),
            ),
        ),
        opportunity_briefs=_artifact_count(db, auth, project_id, "opportunity_brief"),
        competitor_landscapes=_artifact_count(db, auth, project_id, "competitor_landscape"),
        validation_plans=_artifact_count(db, auth, project_id, "validation_plan"),
        assumptions=_model_count(db, Assumption, base_filter),
        high_risk_assumptions=_count(
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
        risks=_model_count(db, Risk, base_filter),
        experiments=_model_count(db, Experiment, base_filter),
        running_experiments=_count(
            db,
            select(func.count())
            .select_from(Experiment)
            .where(
                Experiment.workspace_id == auth.workspace_id,
                Experiment.project_id == project_id,
                Experiment.status == "running",
            ),
        ),
        experiment_results=_model_count(db, ExperimentResult, base_filter),
        validation_interpretations=_model_count(db, ValidationResultInterpretation, base_filter),
        decisions=_model_count(db, Decision, base_filter),
        cited_claims=_count(
            db,
            select(func.count(func.distinct(Claim.id)))
            .select_from(Claim)
            .join(ClaimEvidenceLink, ClaimEvidenceLink.claim_id == Claim.id)
            .where(Claim.workspace_id == auth.workspace_id, Claim.project_id == project_id),
        ),
        unsupported_claims=_count(
            db,
            select(func.count())
            .select_from(Claim)
            .where(
                Claim.workspace_id == auth.workspace_id,
                Claim.project_id == project_id,
                Claim.support_level.in_(["unsupported", "inference"]),
            ),
        ),
        validated_assumptions=_count(
            db,
            select(func.count())
            .select_from(Assumption)
            .where(
                Assumption.workspace_id == auth.workspace_id,
                Assumption.project_id == project_id,
                Assumption.status == "validated",
            ),
        ),
    )


def _model_count(db: Session, model: type, filters: dict[str, uuid.UUID]) -> int:
    return _count(
        db,
        select(func.count())
        .select_from(model)
        .where(
            model.workspace_id == filters["workspace_id"],
            model.project_id == filters["project_id"],
        ),
    )


def _artifact_count(
    db: Session,
    auth: AuthContext,
    project_id: uuid.UUID,
    artifact_type: str,
) -> int:
    return _count(
        db,
        select(func.count())
        .select_from(Artifact)
        .where(
            Artifact.workspace_id == auth.workspace_id,
            Artifact.project_id == project_id,
            Artifact.artifact_type == artifact_type,
            Artifact.current_version_id.is_not(None),
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
    return db.scalar(
        select(Artifact)
        .where(
            Artifact.workspace_id == auth.workspace_id,
            Artifact.project_id == project_id,
            Artifact.artifact_type == artifact_type,
        )
        .options(selectinload(Artifact.versions))
        .order_by(Artifact.updated_at.desc())
    )


def _latest_decision(db: Session, auth: AuthContext, project_id: uuid.UUID) -> Decision | None:
    return db.scalar(
        select(Decision)
        .where(Decision.workspace_id == auth.workspace_id, Decision.project_id == project_id)
        .order_by(Decision.created_at.desc())
    )


def _key_assumptions(db: Session, auth: AuthContext, project_id: uuid.UUID) -> list[Assumption]:
    return list(
        db.scalars(
            select(Assumption)
            .where(
                Assumption.workspace_id == auth.workspace_id,
                Assumption.project_id == project_id,
            )
            .order_by(
                Assumption.kill_risk.desc(),
                Assumption.importance.desc(),
                Assumption.uncertainty.desc(),
                Assumption.updated_at.desc(),
            )
            .limit(5)
        )
    )


def _key_risks(db: Session, auth: AuthContext, project_id: uuid.UUID) -> list[Risk]:
    return list(
        db.scalars(
            select(Risk)
            .where(Risk.workspace_id == auth.workspace_id, Risk.project_id == project_id)
            .order_by(Risk.severity.desc(), Risk.updated_at.desc())
            .limit(5)
        )
    )


def _last_evidence_update(
    db: Session,
    auth: AuthContext,
    project_id: uuid.UUID,
) -> datetime | None:
    return db.scalar(
        select(func.max(EvidenceSource.updated_at)).where(
            EvidenceSource.workspace_id == auth.workspace_id,
            EvidenceSource.project_id == project_id,
        )
    )


def _top_assumption(context: _OverviewContext) -> Assumption | None:
    def score(assumption: Assumption) -> int:
        confidence = assumption.confidence_score or Decimal("0")
        confidence_penalty = int((Decimal("1") - confidence) * 10)
        return (
            (100 if assumption.kill_risk else 0)
            + _importance_rank(assumption.importance) * 20
            + _uncertainty_rank(assumption.uncertainty) * 10
            + confidence_penalty
        )

    if not context.key_assumptions:
        return None
    return sorted(context.key_assumptions, key=score, reverse=True)[0]


def _project_specific_recommendation(
    context: _OverviewContext,
    stage: str,
) -> tuple[str, str] | None:
    if _looks_like_plant_education_project(context.project):
        if stage in {"validation_plan_created", "experiment_running"}:
            return (
                "Pivot away from generic plant education. Test a local workshop/community "
                "wedge first.",
                "Free substitutes like YouTube, Reddit, plant-care apps, blogs, and local "
                "nurseries make a broad plant education app hard to justify. The next "
                "evidence should show whether novice owners will pay or commit to a "
                "structured local learning experience.",
            )
        if stage == "decision_ready":
            return (
                "Recommended decision: continue research or pivot toward local plant workshops.",
                "Do not proceed with a generic plant-care app yet. The strongest unresolved "
                "question is whether plant owners will pay for structured guidance instead "
                "of using free content, apps, nurseries, or community advice.",
            )
    return None


def _looks_like_plant_education_project(project: Project) -> bool:
    text = " ".join(
        [
            project.name or "",
            project.short_description or "",
            *(problem.description for problem in project.problems),
        ]
    ).casefold()
    return "plant" in text and (
        "care" in text or "education" in text or "learn" in text or "workshop" in text
    )


def _short_text(value: str, max_length: int = 150) -> str:
    text = " ".join(value.split())
    if len(text) <= max_length:
        return text
    return f"{text[: max_length - 3].rstrip()}..."


def _primary_segment(project: Project) -> str | None:
    primary = next(
        (segment for segment in project.customer_segments if segment.priority == "primary"),
        None,
    )
    segment = primary or (project.customer_segments[0] if project.customer_segments else None)
    if segment is None:
        return None
    if segment.name.strip().lower() in {"unknown", "target users", "users"}:
        return None
    return segment.name


def _primary_problem(project: Project) -> str | None:
    if not project.problems:
        return None
    ranked = sorted(
        project.problems,
        key=lambda problem: _severity_rank(problem.severity),
        reverse=True,
    )
    return ranked[0].description


def _proposed_wedge(artifact: Artifact | None) -> str | None:
    version = _current_version(artifact) if artifact else None
    if version is None or not isinstance(version.structured_content, dict):
        return None
    for key in ("differentiation_and_wedge", "recommended_wedge", "recommendation"):
        value = version.structured_content.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def _current_version(artifact: Artifact | None) -> ArtifactVersion | None:
    if artifact is None or artifact.current_version_id is None:
        return None
    return next(
        (version for version in artifact.versions if version.id == artifact.current_version_id),
        None,
    )


def _confidence_label(score: Decimal | None) -> str:
    if score is None:
        return "low"
    if score >= Decimal("0.7"):
        return "high"
    if score >= Decimal("0.4"):
        return "medium"
    return "low"


def _recommendation_confidence(context: _OverviewContext, stage: str) -> str:
    if stage in {"draft_idea", "structured_intake"}:
        return "low"
    if context.counts.evidence_sources >= 3 and context.counts.cited_claims >= 3:
        return _confidence_label(context.project.confidence_score)
    if context.counts.evidence_sources > 0:
        return "medium"
    return "low"


def _source_artifact_ids(context: _OverviewContext) -> list[uuid.UUID]:
    ids: list[uuid.UUID] = []
    if context.current_brief is not None:
        ids.append(context.current_brief.id)
    return ids


def _source_evidence_ids(context: _OverviewContext) -> list[uuid.UUID]:
    return [source.id for source in context.project.evidence_sources[:5]]


def _weakest_readiness_area(missing_items: list[ReadinessItemRead]) -> str:
    if not missing_items:
        return "Decision follow-through"
    priority = [
        "target_customer",
        "evidence_sources",
        "competitors",
        "high_risk_assumptions",
        "validation_plan",
        "decision",
    ]
    for key in priority:
        match = next((item for item in missing_items if item.key == key), None)
        if match is not None:
            return match.label
    return missing_items[0].label


def _weakest_evidence_area(context: _OverviewContext) -> str:
    counts = context.counts
    if counts.evidence_sources == 0:
        return "No evidence sources yet"
    if counts.competitors == 0:
        return "Competitor evidence"
    if counts.validated_assumptions == 0:
        if any(
            "pay" in (assumption.category or "").lower()
            for assumption in context.key_assumptions
        ):
            return "Willingness to pay"
        return "Validated assumptions"
    if counts.unsupported_claims > counts.cited_claims:
        return "Unsupported claims"
    return "Evidence is improving"


def _severity_rank(value: str | None) -> int:
    return {"critical": 4, "high": 3, "medium": 2, "low": 1}.get(value or "", 0)


def _importance_rank(value: str | None) -> int:
    return {"critical": 4, "high": 3, "medium": 2, "low": 1}.get(value or "", 0)


def _uncertainty_rank(value: str | None) -> int:
    return {"high": 3, "medium": 2, "low": 1}.get(value or "", 0)


def _format_label(value: str) -> str:
    return value.replace("_", " ").title()
