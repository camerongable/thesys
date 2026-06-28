"""Deterministic decision recommendation shaping helpers."""

import uuid
from typing import Any

from app.db.models import (
    Assumption,
    EvidenceSource,
    Experiment,
    Risk,
    ValidationMission,
    ValidationResultInterpretation,
)
from app.schemas.validation import (
    DecisionCoachActionRead,
    DecisionEvidenceLabelRead,
    SuggestedDecisionRecordRead,
)


def decision_context_domain(
    *,
    assumptions: list[Assumption],
    risks: list[Risk],
    evidence_sources: list[EvidenceSource],
    experiments: list[Experiment],
    interpretation: ValidationResultInterpretation | None,
    mission: ValidationMission | None,
    recommendation: str,
    supporting_evidence: list[str],
    missing_evidence: list[str],
    risk_texts: list[str],
) -> dict[str, Any]:
    return {
        "recommendation": recommendation,
        "supporting_evidence": supporting_evidence,
        "missing_evidence": missing_evidence,
        "risks": risk_texts,
        "inputs": {
            "assumption_count": len(assumptions),
            "risk_count": len(risks),
            "evidence_source_count": len(evidence_sources),
            "experiment_count": len(experiments),
            "logged_result_count": sum(len(experiment.results) for experiment in experiments),
            "has_latest_interpretation": interpretation is not None,
            "has_validation_mission": mission is not None,
        },
        "top_assumptions": [
            {
                "id": str(assumption.id),
                "text": _shorten(assumption.text, 300),
                "status": assumption.status,
                "importance": assumption.importance,
                "uncertainty": assumption.uncertainty,
                "kill_risk": assumption.kill_risk,
                "confidence_score": str(assumption.confidence_score)
                if assumption.confidence_score is not None
                else None,
            }
            for assumption in assumptions[:6]
        ],
        "open_risks": [
            {
                "id": str(risk.id),
                "text": _shorten(risk.text, 260),
                "severity": risk.severity,
                "likelihood": risk.likelihood,
                "status": risk.status,
            }
            for risk in risks[:5]
        ],
        "latest_interpretation": decision_interpretation_context(interpretation),
        "active_validation_mission": decision_mission_context(mission),
    }


def decision_interpretation_context(
    interpretation: ValidationResultInterpretation | None,
) -> dict[str, Any] | None:
    if interpretation is None:
        return None
    return {
        "id": str(interpretation.id),
        "signal_summary": _shorten(interpretation.signal_summary, 400),
        "pain_severity": interpretation.pain_severity,
        "urgency": interpretation.urgency,
        "willingness_to_pay": interpretation.willingness_to_pay,
        "switching_signal": interpretation.switching_signal,
        "confidence_change": interpretation.confidence_change,
        "decision_recommendation": interpretation.decision_recommendation,
        "recommended_next_action": _shorten(interpretation.recommended_next_action, 320),
        "what_strengthened": [_shorten(item, 220) for item in interpretation.what_strengthened[:4]],
        "what_weakened": [_shorten(item, 220) for item in interpretation.what_weakened[:4]],
    }


def decision_mission_context(mission: ValidationMission | None) -> dict[str, Any] | None:
    if mission is None:
        return None
    return {
        "id": str(mission.id),
        "assumption_id": str(mission.assumption_id),
        "experiment_id": str(mission.experiment_id) if mission.experiment_id is not None else None,
        "mission_title": mission.mission_title,
        "target_user": _shorten(mission.target_user, 240),
        "test_type": mission.test_type,
        "success_criteria": _shorten(mission.success_criteria, 260),
        "failure_criteria": _shorten(mission.failure_criteria, 260),
        "status": mission.status,
    }


def decision_context_untrusted_inputs(
    *,
    evidence_sources: list[EvidenceSource],
    interpretation: ValidationResultInterpretation | None,
    experiments: list[Experiment],
) -> list[dict[str, Any]]:
    inputs: list[dict[str, Any]] = []
    for source in evidence_sources[:6]:
        content = source.summary or source.raw_text or source.title or ""
        inputs.append(
            {
                "type": "evidence",
                "title": source.title or f"Evidence source {source.id}",
                "content": _shorten(content, 700),
                "source": "decision_evidence_source",
                "metadata": {
                    "source_id": str(source.id),
                    "source_type": source.source_type,
                    "url": source.url,
                    "classification": source.classification,
                    "credibility_score": str(source.credibility_score)
                    if source.credibility_score is not None
                    else None,
                },
            }
        )
    if interpretation is not None:
        inputs.append(
            {
                "type": "validation",
                "title": "Latest validation interpretation",
                "content": _shorten(interpretation.raw_notes, 900),
                "source": "validation_result_interpretation",
                "metadata": {"interpretation_id": str(interpretation.id)},
            }
        )
    for experiment in experiments[:4]:
        if not experiment.results:
            continue
        latest_result = experiment.results[0]
        inputs.append(
            {
                "type": "validation",
                "title": f"Experiment result: {experiment.name}",
                "content": _shorten(
                    latest_result.raw_notes or latest_result.result_summary,
                    700,
                ),
                "source": "experiment_result",
                "metadata": {
                    "experiment_id": str(experiment.id),
                    "result_id": str(latest_result.id),
                    "outcome": latest_result.outcome,
                },
            }
        )
    return inputs


def decision_recommendation_value(
    *,
    assumptions: list[Assumption],
    experiments: list[Experiment],
    interpretation: ValidationResultInterpretation | None,
) -> str:
    if interpretation is not None:
        if (
            interpretation.decision_recommendation == "proceed"
            and interpretation.willingness_to_pay in {"medium", "strong"}
            and interpretation.switching_signal in {"medium", "strong"}
        ):
            return "proceed"
        if interpretation.decision_recommendation in {"pivot", "pause", "kill"}:
            return interpretation.decision_recommendation
        return "continue_research"
    if any(experiment.results for experiment in experiments):
        return "continue_research"
    if any(
        assumption.status == "invalidated" and assumption.kill_risk for assumption in assumptions
    ):
        return "pivot"
    return "continue_research"


def decision_supporting_evidence(
    *,
    assumptions: list[Assumption],
    evidence_sources: list[EvidenceSource],
    experiments: list[Experiment],
    interpretation: ValidationResultInterpretation | None,
) -> list[str]:
    evidence: list[str] = []
    if interpretation is not None:
        evidence.append(_shorten(interpretation.signal_summary, 240))
        evidence.extend(_shorten(item, 240) for item in interpretation.what_strengthened[:3])
        if interpretation.quotes:
            evidence.append(f"Validation quote: {_shorten(interpretation.quotes[0], 200)}")
    for experiment in experiments:
        if experiment.results:
            latest_result = experiment.results[0]
            evidence.append(
                f"Logged result for {experiment.name}: "
                f"{_shorten(latest_result.result_summary, 180)}"
            )
            break
    validated = next((item for item in assumptions if item.status == "validated"), None)
    if validated is not None:
        evidence.append(f"Validated blocker: {_shorten(validated.text, 180)}")
    if evidence_sources:
        evidence.append(
            f"{len(evidence_sources)} evidence source"
            f"{'' if len(evidence_sources) == 1 else 's'} in the project trail."
        )
    return dedupe_strings(evidence)[:6]


def decision_missing_evidence(
    *,
    assumptions: list[Assumption],
    evidence_sources: list[EvidenceSource],
    experiments: list[Experiment],
    interpretation: ValidationResultInterpretation | None,
    mission: ValidationMission | None,
) -> list[str]:
    missing: list[str] = []
    if not evidence_sources:
        missing.append("Add source-backed evidence for the core customer and market claim.")
    if not assumptions:
        missing.append("Identify the biggest unknown or must-be-true blocker.")
    if mission is None:
        missing.append("Create a validation mission tied to the top blocker.")
    if not any(experiment.results for experiment in experiments):
        missing.append("Log real validation results before recording a proceed decision.")
    if interpretation is None:
        missing.append("Interpret validation notes/results before changing the decision.")
    else:
        if interpretation.willingness_to_pay not in {"medium", "strong"}:
            missing.append(
                "Get stronger willingness-to-pay proof from target users or a pilot commitment."
            )
        if interpretation.switching_signal not in {"medium", "strong"}:
            missing.append("Show that users will switch from their current workaround.")
        if interpretation.pain_severity not in {"medium", "high"}:
            missing.append("Confirm the problem is painful and frequent enough to matter.")
    return dedupe_strings(missing)


def decision_risks(
    assumptions: list[Assumption],
    risks: list[Risk],
    interpretation: ValidationResultInterpretation | None,
) -> list[str]:
    risk_texts = [
        _shorten(assumption.text, 220)
        for assumption in assumptions
        if assumption.kill_risk and assumption.status != "validated"
    ]
    risk_texts.extend(_shorten(risk.text, 220) for risk in risks[:3])
    if interpretation is not None:
        risk_texts.extend(_shorten(item, 220) for item in interpretation.what_weakened[:2])
        risk_texts.extend(_shorten(item, 220) for item in interpretation.objections[:2])
    return dedupe_strings(risk_texts)[:7]


def decision_recommendation_rationale(
    *,
    recommendation: str,
    supporting_evidence: list[str],
    missing_evidence: list[str],
    interpretation: ValidationResultInterpretation | None,
) -> str:
    if recommendation == "proceed":
        return (
            "Proceed only with the narrow wedge that was validated. The latest result "
            "shows enough pain, willingness to pay, and switching signal to justify a "
            "small build or pilot."
        )
    if recommendation == "pivot":
        return (
            "Pivot before building. The current validation signal weakens the existing "
            "wedge, so the next move is to change the target user, problem focus, or "
            "positioning and run a sharper test."
        )
    if recommendation == "pause":
        return (
            "Pause active work until new evidence changes the picture. The current "
            "evidence does not justify more execution effort."
        )
    if recommendation == "kill":
        return (
            "Kill the current version if the blocker is invalidated and another small "
            "test is unlikely to change the conclusion."
        )
    if interpretation is not None:
        return (
            "Continue research. The validation result produced useful learning, but "
            "there is not enough decision-grade proof to proceed yet."
        )
    if supporting_evidence and missing_evidence:
        return (
            "Continue research. Some project evidence exists, but the missing proof is "
            "still material to a build, pivot, pause, or kill decision."
        )
    return (
        "Continue research. The project does not yet have enough validation evidence "
        "to support a durable proceed, pivot, pause, or kill decision."
    )


def decision_evidence_labels(
    *,
    recommendation: str,
    supporting_evidence: list[str],
    missing_evidence: list[str],
    interpretation: ValidationResultInterpretation | None,
) -> list[DecisionEvidenceLabelRead]:
    labels: list[DecisionEvidenceLabelRead] = []
    if recommendation == "proceed" and not missing_evidence:
        labels.append(
            DecisionEvidenceLabelRead(
                id="decision_ready",
                label="Decision-ready evidence",
                severity="success",
                reason="Validation evidence is strong enough for a narrow proceed decision.",
            )
        )
    if not supporting_evidence:
        labels.append(
            DecisionEvidenceLabelRead(
                id="no_supporting_evidence",
                label="No supporting evidence",
                severity="warning",
                reason="The project needs source-backed or validation evidence before a decision.",
            )
        )
    elif missing_evidence:
        labels.append(
            DecisionEvidenceLabelRead(
                id="weak_evidence",
                label="Weak evidence",
                severity="warning",
                reason="Some evidence exists, but missing proof is still material.",
            )
        )
    if interpretation is not None and recommendation != "proceed":
        labels.append(
            DecisionEvidenceLabelRead(
                id="weak_validation_signal",
                label="Weak validation signal",
                severity="warning",
                reason="The latest interpreted validation signal is not strong enough to proceed.",
            )
        )
    return _dedupe_evidence_labels(labels)


def suggested_decision_record(
    *,
    recommendation: str,
    rationale: str,
    supporting_evidence: list[str],
    missing_evidence: list[str],
    risks: list[str],
    assumptions: list[Assumption],
    risks_rows: list[Risk],
    evidence_sources: list[EvidenceSource],
    experiments: list[Experiment],
    interpretation: ValidationResultInterpretation | None,
    mission: ValidationMission | None,
) -> SuggestedDecisionRecordRead:
    decision_type = decision_type_for_recommendation(recommendation)
    title = decision_title_for_recommendation(recommendation)
    revisit_trigger = decision_revisit_trigger(recommendation, mission)
    linked_assumption_ids = decision_linked_assumption_ids(assumptions, interpretation, mission)
    linked_experiment_ids = decision_linked_experiment_ids(experiments, interpretation, mission)
    record_rationale = decision_record_markdown(
        rationale=rationale,
        supporting_evidence=supporting_evidence,
        missing_evidence=missing_evidence,
        risks=risks,
    )
    expected_outcome = (
        f"{decision_expected_outcome(recommendation)}\n\nRevisit trigger: {revisit_trigger}"
    )
    return SuggestedDecisionRecordRead(
        decision_type=decision_type,
        title=title,
        rationale=record_rationale,
        expected_outcome=expected_outcome,
        revisit_trigger=revisit_trigger,
        linked_assumption_ids=linked_assumption_ids,
        linked_risk_ids=[risk.id for risk in risks_rows[:2]],
        linked_evidence_source_ids=[source.id for source in evidence_sources[:3]],
        linked_artifact_ids=[],
        linked_competitor_ids=[],
        linked_experiment_ids=linked_experiment_ids,
        validation_mission_id=mission.id if mission is not None else None,
    )


def decision_linked_assumption_ids(
    assumptions: list[Assumption],
    interpretation: ValidationResultInterpretation | None,
    mission: ValidationMission | None,
) -> list[uuid.UUID]:
    ids: list[uuid.UUID] = []
    if interpretation is not None and interpretation.assumption_id is not None:
        ids.append(interpretation.assumption_id)
    if mission is not None:
        ids.append(mission.assumption_id)
    if assumptions:
        ids.append(assumptions[0].id)
    return dedupe_uuids(ids)[:3]


def decision_linked_experiment_ids(
    experiments: list[Experiment],
    interpretation: ValidationResultInterpretation | None,
    mission: ValidationMission | None,
) -> list[uuid.UUID]:
    ids: list[uuid.UUID] = []
    if interpretation is not None and interpretation.experiment_id is not None:
        ids.append(interpretation.experiment_id)
    if mission is not None and mission.experiment_id is not None:
        ids.append(mission.experiment_id)
    ids.extend(experiment.id for experiment in experiments if experiment.results)
    return dedupe_uuids(ids)[:3]


def decision_action_cards(
    project_id: uuid.UUID,
    recommendation: str,
    has_mission: bool,
) -> list[DecisionCoachActionRead]:
    actions = [
        DecisionCoachActionRead(
            id="prepare_recommended_record",
            label="Prepare recommended record",
            description="Prefill the decision record from this recommendation.",
            target_route=f"/projects/{project_id}#record-decision-panel",
            target_modal="record-decision-panel",
        ),
        DecisionCoachActionRead(
            id="show_blocker_evidence",
            label="Show evidence behind the blocker",
            description="Review the evidence and validation trail behind this decision.",
            target_route=f"/projects/{project_id}#evidence",
        ),
    ]
    if has_mission and recommendation != "proceed":
        actions.insert(
            1,
            DecisionCoachActionRead(
                id="open_validation_mission",
                label="Open validation mission",
                description="Run or inspect the blocker test before deciding.",
                target_route=f"/projects/{project_id}#validation-mission",
                target_modal="validation-mission",
            ),
        )
    return actions


def decision_record_markdown(
    *,
    rationale: str,
    supporting_evidence: list[str],
    missing_evidence: list[str],
    risks: list[str],
) -> str:
    sections = [rationale]
    if supporting_evidence:
        sections.append(
            "Supporting evidence:\n" + "\n".join(f"- {item}" for item in supporting_evidence)
        )
    if missing_evidence:
        sections.append("Missing proof:\n" + "\n".join(f"- {item}" for item in missing_evidence))
    if risks:
        sections.append("Risks:\n" + "\n".join(f"- {item}" for item in risks[:5]))
    return "\n\n".join(sections)


def decision_type_for_recommendation(recommendation: str) -> str:
    return {
        "proceed": "build",
        "pivot": "pivot",
        "pause": "pause",
        "kill": "kill",
        "continue_research": "run_experiment",
    }[recommendation]


def decision_title_for_recommendation(recommendation: str) -> str:
    return {
        "proceed": "Proceed with a narrow validated wedge",
        "pivot": "Pivot from the current wedge",
        "pause": "Pause until evidence improves",
        "kill": "Kill the current idea",
        "continue_research": "Continue research before building",
    }[recommendation]


def decision_expected_outcome(recommendation: str) -> str:
    return {
        "proceed": "Start a narrow build or pilot tied to the validated wedge.",
        "pivot": "Change the wedge, target user, or positioning before further build work.",
        "pause": "Stop active work until a specific new learning goal appears.",
        "kill": "Stop active work and preserve the decision trail for future reference.",
        "continue_research": (
            "Run the next validation test and revisit the decision with stronger proof."
        ),
    }[recommendation]


def decision_revisit_trigger(
    recommendation: str,
    mission: ValidationMission | None,
) -> str:
    if recommendation == "proceed":
        return "Revisit if pilot users do not activate, pay, or switch as expected."
    if recommendation == "pivot":
        return (
            "Revisit after a new wedge has a cleaner pain, urgency, or willingness-to-pay signal."
        )
    if recommendation == "pause":
        return "Revisit only when new evidence changes the biggest unknown."
    if recommendation == "kill":
        return "Reopen only if a materially different target user, wedge, or market signal appears."
    if mission is not None:
        return f"Revisit after completing: {mission.mission_title}."
    return "Revisit after direct validation results are logged and interpreted."


def decision_recommendation_label(recommendation: str) -> str:
    return {
        "proceed": "Proceed",
        "pivot": "Pivot",
        "pause": "Pause",
        "kill": "Kill",
        "continue_research": "Continue research",
    }[recommendation]


def format_bullets(items: list[str]) -> str:
    if not items:
        return "no major gaps are currently flagged"
    return "; ".join(items)


def dedupe_strings(items: list[str]) -> list[str]:
    seen: set[str] = set()
    deduped: list[str] = []
    for item in items:
        normalized = _normalize_key(item)
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        deduped.append(item)
    return deduped


def dedupe_uuids(items: list[uuid.UUID]) -> list[uuid.UUID]:
    seen: set[uuid.UUID] = set()
    deduped: list[uuid.UUID] = []
    for item in items:
        if item in seen:
            continue
        seen.add(item)
        deduped.append(item)
    return deduped


def _dedupe_evidence_labels(
    items: list[DecisionEvidenceLabelRead],
) -> list[DecisionEvidenceLabelRead]:
    seen: set[str] = set()
    deduped: list[DecisionEvidenceLabelRead] = []
    for item in items:
        if item.id in seen:
            continue
        seen.add(item.id)
        deduped.append(item)
    return deduped


def _shorten(value: str, max_length: int) -> str:
    stripped = " ".join(value.split())
    return stripped if len(stripped) <= max_length else f"{stripped[: max_length - 3]}..."


def _normalize_key(value: str) -> str:
    return " ".join(value.casefold().split())
