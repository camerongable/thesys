# ruff: noqa: E501

import uuid
from dataclasses import dataclass
from datetime import UTC, date, datetime
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.auth import AuthContext
from app.core.config import Settings
from app.db.models import (
    AIRun,
    AIStep,
    Artifact,
    ArtifactVersion,
    Assumption,
    Claim,
    ClaimEvidenceLink,
    Competitor,
    CompetitorEvidenceLink,
    CustomerSegment,
    Decision,
    DecisionLink,
    EvidenceSource,
    Experiment,
    ExperimentResult,
    Problem,
    Project,
    Risk,
    ValidationMission,
)
from app.schemas.demo import DemoSeedCounts, DemoSeedRead
from app.schemas.evidence import EvidenceNoteCreate
from app.schemas.projects import ProjectCreate, ProjectRead
from app.schemas.validation import ExperimentResultCreate
from app.services import ai_run_service, evidence_service, project_service, validation_service

DEMO_PROJECT_NAME = "[Demo] Fitness Coach Intelligence OS"
DEMO_IDEA = (
    "An AI platform for independent fitness coaches that turns client check-ins, wearable "
    "data, and workout logs into adaptive training recommendations and client communication drafts."
)


@dataclass(frozen=True)
class _SeedContext:
    project: Project
    evidence: list[EvidenceSource]
    run: AIRun


def seed_demo_project(
    db: Session,
    auth: AuthContext,
    settings: Settings,
) -> DemoSeedRead:
    existing = _find_demo_project(db, auth)
    if existing is not None:
        project = project_service.get_project(db, auth, existing.id)
        return _read_result(db, auth, project, created=False)

    project = project_service.create_project(
        db,
        auth,
        ProjectCreate(
            name=DEMO_PROJECT_NAME,
            short_description=DEMO_IDEA,
            initial_thesis=(
                "Independent online fitness coaches may pay for a workspace that synthesizes "
                "client check-ins, wearable signals, and workout logs into coaching decisions."
            ),
        ),
    )
    _write_structured_project_state(db, auth, project)
    evidence = _write_demo_evidence(db, auth, settings, project.id)
    run = _start_demo_run(db, auth, project.id)
    context = _SeedContext(project=project, evidence=evidence, run=run)
    assumptions, risks = _write_assumptions_and_risks(db, auth, context)
    competitors = _write_competitors(db, auth, context)
    artifacts = _write_artifacts(db, auth, context, assumptions, risks, competitors)
    experiment = _write_experiment_result(db, auth, project.id, assumptions[0])
    decision = _write_decision(db, auth, project.id, assumptions, artifacts, experiment)
    _complete_demo_run(
        db, run, evidence, assumptions, risks, competitors, artifacts, experiment, decision
    )
    project = project_service.get_project(db, auth, project.id)
    return _read_result(db, auth, project, created=True)


def _find_demo_project(db: Session, auth: AuthContext) -> Project | None:
    return db.scalar(
        select(Project).where(
            Project.workspace_id == auth.workspace_id,
            Project.name == DEMO_PROJECT_NAME,
        )
    )


def _write_structured_project_state(db: Session, auth: AuthContext, project: Project) -> None:
    project.confidence_score = Decimal("0.52")
    online = CustomerSegment(
        workspace_id=auth.workspace_id,
        project_id=project.id,
        name="Independent online fitness coaches",
        description=(
            "Solo coaches managing recurring check-ins, programming, and client messages across "
            "several tools."
        ),
        buyer_type="prosumer",
        priority="primary",
        confidence_score=Decimal("0.62"),
    )
    trainers = CustomerSegment(
        workspace_id=auth.workspace_id,
        project_id=project.id,
        name="Solo personal trainers expanding online",
        description="Trainers moving from in-person sessions into hybrid or remote coaching.",
        buyer_type="prosumer",
        priority="secondary",
        confidence_score=Decimal("0.44"),
    )
    db.add_all([online, trainers])
    db.flush()
    db.add_all(
        [
            Problem(
                workspace_id=auth.workspace_id,
                project_id=project.id,
                segment_id=online.id,
                description=(
                    "Coaches spend repeated weekly time reviewing check-ins and translating "
                    "scattered client data into next actions."
                ),
                severity="high",
                frequency="Weekly",
                current_alternatives="Spreadsheets, messaging apps, notes, and coaching platforms.",
                confidence_score=Decimal("0.58"),
            ),
            Problem(
                workspace_id=auth.workspace_id,
                project_id=project.id,
                segment_id=online.id,
                description=(
                    "Progress data is spread across workout logs, wearables, forms, and chat, "
                    "which makes it hard to keep a consistent client view."
                ),
                severity="medium",
                frequency="Several times per week",
                current_alternatives="Manual review and generic automation templates.",
                confidence_score=Decimal("0.48"),
            ),
        ]
    )
    thesis = project_service.current_thesis(project)
    if thesis:
        thesis.rationale = "Seeded from the MVP demo scenario in the implementation brief."
        thesis.confidence_score = Decimal("0.52")
    db.commit()


def _write_demo_evidence(
    db: Session,
    auth: AuthContext,
    settings: Settings,
    project_id: uuid.UUID,
) -> list[EvidenceSource]:
    notes = [
        (
            "Customer discovery notes: online coach workflow",
            (
                "Interview notes from three independent online fitness coaches. Coaches described "
                "spending 3 to 6 hours each week reviewing check-in forms, workout adherence, "
                "sleep notes, and client messages before deciding whether to change programming. "
                "Two coaches said they already use spreadsheets plus Trainerize or TrueCoach, but "
                "still write most client feedback manually. All three wanted recommendations to "
                "show rationale before they would trust AI-generated changes."
            ),
        ),
        (
            "Competitor notes: coaching platforms",
            (
                "Trainerize, TrueCoach, Everfit, and similar coaching tools help coaches deliver "
                "workouts, habits, messages, and progress tracking. Their core value is client "
                "management and program delivery. The perceived gap is not storage of workout data; "
                "it is synthesis across check-ins, subjective notes, wearable signals, and the "
                "coach's decision history."
            ),
        ),
        (
            "Validation notes: willingness to pay",
            (
                "A pricing conversation with two solo coaches suggested willingness to pay may exist "
                "if the product saves at least two hours per week and keeps final recommendations "
                "under coach control. One coach rejected fully automated programming, but reacted "
                "positively to draft recommendations with citations to client data and prior notes."
            ),
        ),
    ]
    sources: list[EvidenceSource] = []
    for title, text in notes:
        source = evidence_service.add_note_source(
            db,
            auth,
            settings,
            project_id,
            EvidenceNoteCreate(title=title, text=text, source_type="note"),
        )
        sources.append(source)
    return sources


def _start_demo_run(db: Session, auth: AuthContext, project_id: uuid.UUID) -> AIRun:
    run = ai_run_service.start_run(
        db,
        auth,
        workflow_type="demo_seed",
        prompt_version="demo-seed-v1",
        input_summary="Seed Sprint 8 end-to-end demo project.",
        project_id=project_id,
        model_provider="internal",
        model_name="deterministic-demo-fixture",
    )
    step = ai_run_service.start_step(
        db,
        run,
        step_name="write_demo_workspace",
        input_json={"scenario": "fitness_coach_intelligence_os"},
    )
    step.output_json = {"status": "started"}
    db.commit()
    return run


def _write_assumptions_and_risks(
    db: Session,
    auth: AuthContext,
    context: _SeedContext,
) -> tuple[list[Assumption], list[Risk]]:
    assumptions = [
        Assumption(
            workspace_id=auth.workspace_id,
            project_id=context.project.id,
            text="Coaches trust AI-generated recommendations when the rationale and source data are visible.",
            category="trust",
            importance="critical",
            uncertainty="high",
            kill_risk=True,
            confidence_score=Decimal("0.46"),
            status="testing",
            recommended_test=(
                "Show draft recommendations with cited check-in data and ask coaches what they "
                "would edit before sending to a client."
            ),
        ),
        Assumption(
            workspace_id=auth.workspace_id,
            project_id=context.project.id,
            text="Independent online coaches lose enough weekly time on check-ins to pay for automation.",
            category="willingness_to_pay",
            importance="high",
            uncertainty="medium",
            kill_risk=True,
            confidence_score=Decimal("0.58"),
            status="untested",
            recommended_test="Run pricing interviews and ask for pilot commitments.",
        ),
        Assumption(
            workspace_id=auth.workspace_id,
            project_id=context.project.id,
            text="A narrow check-in synthesis workflow can differentiate from broad coaching platforms.",
            category="differentiation",
            importance="high",
            uncertainty="medium",
            kill_risk=False,
            confidence_score=Decimal("0.55"),
            status="untested",
            recommended_test="Compare a workflow prototype against Trainerize, TrueCoach, and spreadsheets.",
        ),
    ]
    risks = [
        Risk(
            workspace_id=auth.workspace_id,
            project_id=context.project.id,
            text="Coaches may reject recommendations that appear to replace their judgment.",
            category="trust",
            severity="high",
            likelihood="medium",
            mitigation="Keep the coach in control and show the evidence behind every recommendation.",
            status="open",
        ),
        Risk(
            workspace_id=auth.workspace_id,
            project_id=context.project.id,
            text="Wearable and platform integrations could expand scope before the wedge is validated.",
            category="scope",
            severity="medium",
            likelihood="medium",
            mitigation="Validate the check-in synthesis workflow with pasted/manual data first.",
            status="open",
        ),
    ]
    db.add_all([*assumptions, *risks])
    db.commit()
    return assumptions, risks


def _write_competitors(
    db: Session,
    auth: AuthContext,
    context: _SeedContext,
) -> list[Competitor]:
    first_source = context.evidence[1]
    first_chunk_id = first_source.chunks[0].id if first_source.chunks else None
    competitors = [
        Competitor(
            workspace_id=auth.workspace_id,
            project_id=context.project.id,
            name="Trainerize",
            url="https://www.trainerize.com",
            category="direct",
            target_user="Fitness coaches and trainers managing clients.",
            positioning="All-in-one coaching platform for workouts, habits, messaging, and payments.",
            pricing_summary="Subscription pricing; verify current plans before using in positioning.",
            key_features=["Workout delivery", "Client messaging", "Habit tracking", "Payments"],
            strengths="Known category player with broad coaching workflow coverage.",
            weaknesses="Not positioned primarily around explainable AI synthesis of weekly check-ins.",
            differentiation_notes="Compete on decision synthesis and evidence-backed coaching rationale.",
            threat_level="high",
            watchlist_status="candidate",
            last_analyzed_at=datetime.now(UTC),
        ),
        Competitor(
            workspace_id=auth.workspace_id,
            project_id=context.project.id,
            name="TrueCoach",
            url="https://truecoach.co",
            category="direct",
            target_user="Personal trainers and strength coaches.",
            positioning="Coaching software for programming, workout delivery, and client management.",
            pricing_summary="Subscription pricing; verify source before quoting details.",
            key_features=["Program builder", "Exercise library", "Client tracking"],
            strengths="Clear fit for coaches who need structured program delivery.",
            weaknesses="The demo thesis depends on synthesis across signals, not only program delivery.",
            differentiation_notes="Use check-in intelligence as the wedge instead of a full platform clone.",
            threat_level="medium",
            watchlist_status="candidate",
            last_analyzed_at=datetime.now(UTC),
        ),
        Competitor(
            workspace_id=auth.workspace_id,
            project_id=context.project.id,
            name="Google Sheets plus ChatGPT",
            url=None,
            category="manual_alternative",
            target_user="Budget-conscious solo coaches.",
            positioning="Flexible manual workflow using spreadsheets and generic AI drafting.",
            pricing_summary="Low direct software cost, but high manual time cost.",
            key_features=["Flexible tracking", "Manual synthesis", "Generic drafting"],
            strengths="Low friction and already familiar.",
            weaknesses="Weak persistent client context, citation trail, and decision history.",
            differentiation_notes="Show why a purpose-built workflow is faster and safer than ad hoc chat.",
            threat_level="medium",
            watchlist_status="not_watched",
            last_analyzed_at=datetime.now(UTC),
        ),
    ]
    db.add_all(competitors)
    db.flush()
    for competitor in competitors:
        db.add(
            CompetitorEvidenceLink(
                competitor_id=competitor.id,
                evidence_source_id=first_source.id,
                evidence_chunk_id=first_chunk_id,
            )
        )
    db.commit()
    return competitors


def _write_artifacts(
    db: Session,
    auth: AuthContext,
    context: _SeedContext,
    assumptions: list[Assumption],
    risks: list[Risk],
    competitors: list[Competitor],
) -> list[Artifact]:
    brief = _write_artifact(
        db,
        auth,
        context,
        "opportunity_brief",
        f"{context.project.name} Opportunity Brief",
        _brief_markdown(context, assumptions, risks, competitors),
        {
            "unsupported_claims": [
                "Market size and acquisition cost remain unvalidated until more external research is added.",
                "The exact integration requirements for a first product version still need discovery.",
            ]
        },
    )
    landscape = _write_artifact(
        db,
        auth,
        context,
        "competitor_landscape",
        f"{context.project.name} Competitor Landscape",
        _competitor_markdown(competitors),
        {
            "unsupported_claims": [
                "Competitor pricing and feature depth should be rechecked against live source pages."
            ]
        },
    )
    validation = _write_artifact(
        db,
        auth,
        context,
        "validation_plan",
        f"{context.project.name} Validation Plan",
        _validation_markdown(assumptions),
        {"plans": [assumption.text for assumption in assumptions[:2]]},
    )
    _write_claims(db, auth, context, brief)
    _write_claims(db, auth, context, landscape)
    db.commit()
    return [brief, landscape, validation]


def _write_artifact(
    db: Session,
    auth: AuthContext,
    context: _SeedContext,
    artifact_type: str,
    title: str,
    markdown: str,
    structured: dict,
) -> Artifact:
    artifact = Artifact(
        workspace_id=auth.workspace_id,
        project_id=context.project.id,
        artifact_type=artifact_type,
        title=title,
        created_by=auth.user_id,
    )
    db.add(artifact)
    db.flush()
    version = ArtifactVersion(
        workspace_id=auth.workspace_id,
        artifact_id=artifact.id,
        version=1,
        markdown_content=markdown,
        structured_content=structured,
        generated_by_ai_run_id=context.run.id,
        created_by=auth.user_id,
    )
    db.add(version)
    db.flush()
    artifact.current_version_id = version.id
    artifact.versions = [version]
    return artifact


def _write_claims(
    db: Session, auth: AuthContext, context: _SeedContext, artifact: Artifact
) -> None:
    version = artifact.versions[0]
    source = context.evidence[0]
    chunk = source.chunks[0] if source.chunks else None
    claims = [
        Claim(
            workspace_id=auth.workspace_id,
            project_id=context.project.id,
            artifact_version_id=version.id,
            text=(
                "Discovery notes indicate coaches spend recurring weekly time reviewing "
                "check-ins and client data before making coaching decisions."
            ),
            claim_type="customer_discovery",
            confidence_score=Decimal("0.72"),
            support_level="supported",
        ),
        Claim(
            workspace_id=auth.workspace_id,
            project_id=context.project.id,
            artifact_version_id=version.id,
            text="Trust in recommendations remains a kill-risk assumption until tested directly.",
            claim_type="validation_gap",
            confidence_score=Decimal("0.55"),
            support_level="inference",
        ),
    ]
    db.add_all(claims)
    db.flush()
    db.add(
        ClaimEvidenceLink(
            claim_id=claims[0].id,
            evidence_source_id=source.id,
            evidence_chunk_id=chunk.id if chunk else None,
            relevance_score=Decimal("0.88"),
            quote=(chunk.text[:500] if chunk else source.summary),
        )
    )


def _write_experiment_result(
    db: Session,
    auth: AuthContext,
    project_id: uuid.UUID,
    assumption: Assumption,
) -> Experiment:
    experiment = Experiment(
        workspace_id=auth.workspace_id,
        project_id=project_id,
        assumption_id=assumption.id,
        name="Validate coach trust in cited AI recommendations",
        method="customer_interview",
        plan=(
            "Show five target coaches a mocked recommendation generated from a weekly check-in. "
            "Ask what they trust, what they would edit, and whether rationale/citations change "
            "their willingness to use it."
        ),
        success_criteria=(
            "At least three of five coaches would use an edited recommendation draft in their "
            "workflow and can explain which evidence made it trustworthy."
        ),
        failure_threshold="Fewer than two coaches would use the recommendation even with edits.",
        status="planned",
    )
    db.add(experiment)
    db.flush()
    mission = ValidationMission(
        workspace_id=auth.workspace_id,
        project_id=project_id,
        assumption_id=assumption.id,
        experiment_id=experiment.id,
        mission_title="Prove: coaches will trust cited AI recommendations",
        why_it_matters=(
            "This is the highest-risk decision blocker. Without proof that coaches "
            "trust and use the workflow, building the product is premature."
        ),
        target_user="Independent online fitness coaches",
        test_type="customer_interview",
        steps=[
            "Recruit five independent online fitness coaches.",
            "Show a mocked weekly check-in recommendation with cited rationale.",
            "Ask what they trust, what they would edit, and what they would reject.",
            "Test whether rationale/citations change willingness to use the draft.",
            "Log objections, willingness-to-pay signals, and switching concerns.",
            "Review whether the result supports continue, pivot, pause, or proceed.",
        ],
        success_criteria=experiment.success_criteria or "Three of five coaches show usage intent.",
        failure_criteria=experiment.failure_threshold or "Fewer than two coaches show usage intent.",
        assets=[
            {
                "type": "interview_script",
                "title": "Interview script",
                "content": experiment.plan or "Show the recommendation mock and ask for trust signals.",
            },
            {
                "type": "outreach_message",
                "title": "Outreach message",
                "content": (
                    "I am testing a workflow that turns client check-ins into cited "
                    "recommendation drafts for independent coaches. Would you be open "
                    "to a short feedback call?"
                ),
            },
            {
                "type": "results_rubric",
                "title": "Result interpretation rubric",
                "content": (
                    f"Success: {experiment.success_criteria}\n\n"
                    f"Failure: {experiment.failure_threshold}"
                ),
            },
        ],
        status="planned",
        created_by=auth.user_id,
    )
    db.add(mission)
    db.commit()
    validation_service.log_experiment_result(
        db,
        auth,
        project_id,
        experiment.id,
        ExperimentResultCreate(
            outcome="mixed",
            result_summary=(
                "Two coaches said they would use cited drafts after editing; one rejected "
                "recommendations without tighter control over tone and program changes."
            ),
            raw_notes=(
                "Signal is promising but not validated. Rationale visibility mattered more than "
                "full automation."
            ),
        ),
    )
    return validation_service.get_experiment(db, auth, project_id, experiment.id)


def _write_decision(
    db: Session,
    auth: AuthContext,
    project_id: uuid.UUID,
    assumptions: list[Assumption],
    artifacts: list[Artifact],
    experiment: Experiment,
) -> Decision:
    decision = Decision(
        workspace_id=auth.workspace_id,
        project_id=project_id,
        decision_type="change_icp",
        title="Focus initial validation on independent online coaches",
        rationale=(
            "The strongest current evidence points to solo online coaches with repeated weekly "
            "check-in pain. Gyms and clinics should wait until the first workflow is validated."
        ),
        expected_outcome=(
            "Narrower discovery should clarify trust requirements, weekly time savings, and "
            "willingness to pay before product scope expands."
        ),
        review_date=date(2026, 6, 30),
        created_by=auth.user_id,
    )
    db.add(decision)
    db.flush()
    for linked_type, linked_id in [
        ("assumption", assumptions[0].id),
        ("artifact", artifacts[0].id),
        ("artifact", artifacts[2].id),
        ("experiment", experiment.id),
    ]:
        db.add(DecisionLink(decision_id=decision.id, linked_type=linked_type, linked_id=linked_id))
    db.commit()
    return decision


def _complete_demo_run(
    db: Session,
    run: AIRun,
    evidence: list[EvidenceSource],
    assumptions: list[Assumption],
    risks: list[Risk],
    competitors: list[Competitor],
    artifacts: list[Artifact],
    experiment: Experiment,
    decision: Decision,
) -> None:
    step = db.scalar(select(AIStep).where(AIStep.ai_run_id == run.id))
    if step is not None:
        ai_run_service.complete_step(
            db,
            step,
            output_json={
                "evidence_source_ids": [str(source.id) for source in evidence],
                "assumption_ids": [str(assumption.id) for assumption in assumptions],
                "risk_ids": [str(risk.id) for risk in risks],
                "competitor_ids": [str(competitor.id) for competitor in competitors],
                "artifact_ids": [str(artifact.id) for artifact in artifacts],
                "experiment_id": str(experiment.id),
                "decision_id": str(decision.id),
            },
            latency_ms=0,
            tokens=None,
            cost=Decimal("0"),
        )
    ai_run_service.complete_run(
        db,
        run,
        output_summary="Seeded a complete Sprint 8 demo workspace.",
        total_tokens=None,
        total_cost=Decimal("0"),
        model_provider="internal",
        model_name="deterministic-demo-fixture",
    )


def _read_result(
    db: Session, auth: AuthContext, project: Project, *, created: bool
) -> DemoSeedRead:
    counts = _counts(db, auth, project.id)
    return DemoSeedRead(
        project=ProjectRead.model_validate(
            {
                **project.__dict__,
                "current_thesis": project_service.current_thesis(project),
                "customer_segments": list(project.customer_segments),
                "problems": list(project.problems),
            }
        ),
        created=created,
        counts=counts,
        next_url=f"/projects/{project.id}",
        message=(
            "Created demo project." if created else "Demo project already exists; returned it."
        ),
    )


def _counts(db: Session, auth: AuthContext, project_id: uuid.UUID) -> DemoSeedCounts:
    filters = {"workspace_id": auth.workspace_id, "project_id": project_id}
    return DemoSeedCounts(
        evidence_sources=_model_count(db, EvidenceSource, filters),
        artifacts=_model_count(db, Artifact, filters),
        competitors=_model_count(db, Competitor, filters),
        assumptions=_model_count(db, Assumption, filters),
        risks=_model_count(db, Risk, filters),
        experiments=_model_count(db, Experiment, filters),
        experiment_results=_model_count(db, ExperimentResult, filters),
        decisions=_model_count(db, Decision, filters),
        ai_runs=_model_count(db, AIRun, filters),
    )


def _model_count(db: Session, model: type, filters: dict) -> int:
    return int(
        db.scalar(
            select(func.count())
            .select_from(model)
            .where(
                model.workspace_id == filters["workspace_id"],
                model.project_id == filters["project_id"],
            )
        )
        or 0
    )


def _brief_markdown(
    context: _SeedContext,
    assumptions: list[Assumption],
    risks: list[Risk],
    competitors: list[Competitor],
) -> str:
    competitor_names = ", ".join(competitor.name for competitor in competitors)
    return f"""# {context.project.name} Opportunity Brief

## Executive Summary
Independent online fitness coaches are a plausible first wedge because the seeded evidence shows repeated weekly check-in review work, scattered client data, and concern about trusting fully automated recommendations.

## Product Hypothesis
{DEMO_IDEA}

## Target User / Buyer
Primary: independent online fitness coaches. Secondary: solo personal trainers expanding into online coaching.

## Problem Analysis
Coaches review check-ins, client messages, workout adherence, and wearable signals before deciding whether to adjust training. The pain is recurring and operational, but trust in AI recommendations is still a kill-risk assumption.

## Current Alternatives
Trainerize, TrueCoach, Everfit, spreadsheets, messaging apps, and generic AI drafting.

## Market Context
The market should be treated conservatively until more external sources are added. The useful initial category is coach workflow intelligence, not broad fitness automation.

## Competitor Landscape
Seeded competitors: {competitor_names}. Existing platforms are stronger for program delivery and client management than for explainable synthesis across weekly check-ins.

## Differentiation and Wedge
Start with cited weekly check-in synthesis: draft recommendation, show source signals, keep the coach in control, and preserve decision history.

## Risks and Kill-Risk Assumptions
{assumptions[0].text}

Risk: {risks[0].text}

## Validation Plan
Run five coach interviews using mocked recommendations grounded in sample check-in data. Measure trust, edits required, willingness to pay, and whether evidence citations change adoption intent.

## Recommendation
Proceed with focused validation for independent online coaches before adding gyms, clinics, or deep wearable integrations.

## Evidence Appendix
- Customer discovery notes
- Competitor notes
- Pricing and willingness-to-pay notes

## Unsupported Claims / Open Questions
- Market size and acquisition cost are not yet validated.
- Required integrations for the first version remain open.
"""


def _competitor_markdown(competitors: list[Competitor]) -> str:
    lines = ["# Competitor Landscape", "", "## Profiles"]
    for competitor in competitors:
        lines.extend(
            [
                f"### {competitor.name}",
                f"- Category: {competitor.category}",
                f"- Threat: {competitor.threat_level}",
                f"- Positioning: {competitor.positioning}",
                f"- Differentiation note: {competitor.differentiation_notes}",
                "",
            ]
        )
    lines.extend(
        [
            "## Positioning Gaps",
            "- Explainable check-in synthesis",
            "- Evidence-linked recommendations",
            "- Decision history for coaching changes",
        ]
    )
    return "\n".join(lines)


def _validation_markdown(assumptions: list[Assumption]) -> str:
    return "\n\n".join(
        [
            "# Validation Plan",
            "## Priority Assumption",
            assumptions[0].text,
            "## Method",
            "Customer interviews with recommendation mockups and explicit trust scoring.",
            "## Success Criteria",
            "Three of five coaches would use an edited recommendation draft and can identify the source evidence that made it trustworthy.",
            "## Failure Threshold",
            "Fewer than two coaches would use the draft even after reviewing cited evidence.",
        ]
    )
