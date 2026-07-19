"""Deterministic strategy helpers for bounded agentic research."""

from typing import Any

from app.schemas.evidence import EvidenceRetrievalResultRead


def clean_list(values: list[str]) -> list[str]:
    seen: set[str] = set()
    cleaned: list[str] = []
    for value in values:
        text = " ".join(str(value).split())
        key = text.casefold()
        if text and key not in seen:
            cleaned.append(text)
            seen.add(key)
    return cleaned


def term_set(text: str) -> set[str]:
    return {
        term
        for term in (part.strip(".,:;!?()[]{}\"'").casefold() for part in text.split())
        if len(term) > 2
    }


def plan_subquestions(sprint: Any, *, max_subquestions: int) -> list[str]:
    candidates = [
        *sprint.plan.research_questions,
        f"What evidence supports or weakens this objective: {sprint.plan.objective}",
        "Which competitor or substitute creates the largest positioning risk?",
        "What evidence is missing before deciding what to validate next?",
    ]
    return clean_list(candidates)[:max_subquestions]


def select_tool_calls(
    sprint: Any,
    subquestions: list[str],
    *,
    max_subquestions: int,
    initial_top_k: int,
) -> list[dict[str, Any]]:
    calls: list[dict[str, Any]] = [
        {
            "tool": "project_memory_lookup",
            "query": sprint.plan.objective,
            "mode": "hybrid",
            "top_k": 1,
            "reason": "Load structured project memory before retrieval.",
        },
        {
            "tool": "competitor_lookup",
            "query": "competitors and substitute behaviors",
            "mode": "hybrid",
            "top_k": 8,
            "reason": "Include approved competitor records and candidates.",
        },
        {
            "tool": "artifact_lookup",
            "query": "prior briefs and validation artifacts",
            "mode": "hybrid",
            "top_k": 6,
            "reason": "Use existing artifacts as project memory.",
        },
        {
            "tool": "assumption_lookup",
            "query": "existing assumptions and risks",
            "mode": "hybrid",
            "top_k": 8,
            "reason": "Connect research to current validation priorities.",
        },
    ]
    for index, question in enumerate(subquestions[:max_subquestions]):
        mode = "semantic" if index % 2 == 0 else "keyword"
        calls.append(
            {
                "tool": f"{mode}_search",
                "query": question,
                "mode": mode,
                "top_k": initial_top_k,
                "reason": "Retrieve evidence for a research subquestion.",
            }
        )
    calls.append(
        {
            "tool": "source_reader",
            "query": "approved research sources",
            "mode": "hybrid",
            "top_k": 8,
            "reason": "Read source summaries and snippets before synthesis.",
        }
    )
    return calls


def lookup_tool_name(tool: str) -> str | None:
    if tool == "competitor_lookup":
        return "list_competitors"
    if tool == "artifact_lookup":
        return "get_research_memo"
    if tool == "assumption_lookup":
        return "list_assumptions"
    if tool == "project_memory_lookup":
        return "list_project_memory"
    return None


def lookup_tool_payload(
    project_context: dict[str, Any],
    tool: str,
) -> list[dict[str, Any]]:
    if tool == "competitor_lookup":
        return list(project_context.get("competitors", [])) + list(
            project_context.get("competitor_candidates", [])
        )
    if tool == "artifact_lookup":
        return list(project_context.get("artifacts", []))
    if tool == "assumption_lookup":
        return list(project_context.get("assumptions", []))
    if tool == "project_memory_lookup":
        return list(project_context.get("project_memory", []))
    return []


def detect_gaps(
    subquestions: list[str],
    selected_evidence: list[EvidenceRetrievalResultRead],
    *,
    min_evidence_count: int,
    max_gaps: int,
) -> list[str]:
    gaps: list[str] = []
    evidence_text = " ".join(result.text for result in selected_evidence).casefold()
    for question in subquestions:
        terms = [term for term in term_set(question) if len(term) > 4]
        if not terms or not any(term in evidence_text for term in terms[:5]):
            gaps.append(f"Weak evidence for: {question}")
    if len(selected_evidence) < min_evidence_count:
        gaps.append("Too few retrieved evidence chunks to support a confident memo.")
    has_pricing_signal = any(
        "pricing" in result.text.casefold() or "pay" in result.text.casefold()
        for result in selected_evidence
    )
    if not has_pricing_signal:
        gaps.append("Willingness-to-pay and pricing evidence is still weak.")
    return clean_list(gaps)[:max_gaps]
