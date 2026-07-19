"""Pure eval gate and diagnostic interpretation helpers."""

from dataclasses import dataclass
from typing import Any

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


@dataclass(frozen=True)
class Check:
    key: str
    label: str
    passed: bool
    observed: int | bool | str | None
    expected: str


@dataclass(frozen=True)
class ResearchMetric:
    key: str
    label: str
    passed: bool
    observed: int | bool | str | None
    expected: str


def contains_required_sections(markdown: str) -> bool:
    return all(section.casefold() in markdown.casefold() for section in REQUIRED_BRIEF_SECTIONS)


def section_coverage(markdown: str) -> str:
    covered = sum(
        1 for section in REQUIRED_BRIEF_SECTIONS if section.casefold() in markdown.casefold()
    )
    return f"{covered}/{len(REQUIRED_BRIEF_SECTIONS)}"


def contains_research_memo_sections(markdown: str) -> bool:
    return all(
        section.casefold() in markdown.casefold() for section in REQUIRED_RESEARCH_MEMO_SECTIONS
    )


def research_memo_section_coverage(markdown: str) -> str:
    covered = sum(
        1
        for section in REQUIRED_RESEARCH_MEMO_SECTIONS
        if section.casefold() in markdown.casefold()
    )
    return f"{covered}/{len(REQUIRED_RESEARCH_MEMO_SECTIONS)}"


def diagnostic_items(value: Any) -> list[dict[str, Any]]:
    if isinstance(value, list):
        return [item for item in value if isinstance(item, dict)]
    return []


def has_multi_stage_retrieval(value: Any) -> bool:
    for item in diagnostic_items(value):
        plan = item.get("query_plan")
        if isinstance(plan, dict) and (
            plan.get("decomposed") is True or len(plan.get("subqueries") or []) > 1
        ):
            return True
    return False


def retrieval_strategy_observed(value: Any) -> str:
    items = diagnostic_items(value)
    subquery_count = sum(
        len(item.get("query_plan", {}).get("subqueries") or [])
        for item in items
        if isinstance(item.get("query_plan"), dict)
    )
    return f"{len(items)} diagnostics, {subquery_count} subqueries"


def has_reranker_diagnostics(value: Any) -> bool:
    return any(isinstance(item.get("reranker"), dict) for item in diagnostic_items(value))


def reranker_observed(value: Any) -> str:
    rerankers = [
        item.get("reranker")
        for item in diagnostic_items(value)
        if isinstance(item.get("reranker"), dict)
    ]
    if not rerankers:
        return "no reranker diagnostics"
    enabled_count = sum(1 for reranker in rerankers if reranker.get("enabled") is True)
    providers = sorted({str(reranker.get("provider")) for reranker in rerankers})
    return f"{enabled_count}/{len(rerankers)} enabled, providers: {', '.join(providers)}"


def has_context_assembly(context: Any, diagnostics: Any) -> bool:
    if isinstance(context, dict) and context.get("selected_count", 0) >= 1:
        return True
    return any(
        isinstance(item.get("context"), dict) and item["context"].get("selected_count", 0) >= 1
        for item in diagnostic_items(diagnostics)
    )


def context_assembly_observed(context: Any, diagnostics: Any) -> str:
    if isinstance(context, dict) and context:
        return (
            f"{context.get('selected_count', 0)} selected, "
            f"{context.get('token_count', 0)}/{context.get('token_budget', 0)} tokens"
        )
    contexts = [
        item.get("context")
        for item in diagnostic_items(diagnostics)
        if isinstance(item.get("context"), dict)
    ]
    selected = sum(int(item.get("selected_count") or 0) for item in contexts)
    tokens = sum(int(item.get("token_count") or 0) for item in contexts)
    return f"{selected} selected, {tokens} tokens"


def has_quality_report(value: Any) -> bool:
    return any(isinstance(item.get("quality_report"), dict) for item in diagnostic_items(value))


def quality_report_observed(value: Any) -> str:
    reports = [
        item.get("quality_report")
        for item in diagnostic_items(value)
        if isinstance(item.get("quality_report"), dict)
    ]
    if not reports:
        return "no retrieval quality reports"
    avg_precision = sum(float(report.get("precision_proxy") or 0) for report in reports) / len(
        reports
    )
    avg_recall = sum(float(report.get("recall_proxy") or 0) for report in reports) / len(reports)
    return f"{len(reports)} reports, precision {avg_precision:.2f}, recall {avg_recall:.2f}"
