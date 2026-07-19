"""Research-sprint eval dataset loading and scoring helpers."""

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

from app.features.evals import metric_records
from app.schemas.evals import ResearchEvalCaseRead

REPO_ROOT = Path(__file__).resolve().parents[5]
DEFAULT_DATASET_PATH = REPO_ROOT / "apps/api/app/evals/research_sprint_cases.json"

REQUIRED_CATEGORIES = {
    "B2B SaaS",
    "consumer app",
    "developer tool",
    "fitness/health",
    "local services",
    "marketplace",
    "AI workflow tool",
    "productivity tool",
    "creator/consultant workflow",
    "ecommerce/affiliate idea",
}
REQUIRED_CASE_FIELDS = {
    "id",
    "idea_type",
    "idea",
    "expected_competitor_types",
    "expected_risky_assumptions",
    "required_output_sections",
    "unacceptable_claims",
    "expected_next_action_type",
}


def dataset_path() -> Path:
    """Return the canonical seeded research-sprint eval dataset path."""

    return DEFAULT_DATASET_PATH


def load_raw_cases(path: Path | None = None) -> list[dict[str, Any]]:
    """Load the raw JSON research-sprint eval case dictionaries."""

    case_path = path or dataset_path()
    return json.loads(case_path.read_text(encoding="utf-8"))


@lru_cache(maxsize=1)
def load_research_eval_cases() -> list[ResearchEvalCaseRead]:
    """Load and validate seeded research-sprint eval cases for API responses."""

    return [ResearchEvalCaseRead.model_validate(raw_case) for raw_case in load_raw_cases()]


def score_dataset(cases: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Score seeded research-sprint eval case coverage without a running API."""

    categories = {case.get("idea_type") for case in cases}
    complete_cases = [
        case
        for case in cases
        if REQUIRED_CASE_FIELDS.issubset(case)
        and all(case.get(field) for field in REQUIRED_CASE_FIELDS)
    ]
    demo_ready_count = sum(1 for case in cases if case.get("demo_ready"))
    required_sections = sum(
        1 for case in cases if len(case.get("required_output_sections") or []) >= 4
    )
    safety_cases = sum(1 for case in cases if case.get("unacceptable_claims"))
    next_actions = sum(1 for case in cases if case.get("expected_next_action_type"))
    return [
        metric_records.metric(
            "dataset_case_count",
            "Dataset case count",
            len(cases) >= 10,
            len(cases),
            "10+",
        ),
        metric_records.metric(
            "category_coverage",
            "Category coverage",
            REQUIRED_CATEGORIES.issubset(categories),
            f"{len(categories)}/{len(REQUIRED_CATEGORIES)}",
            "all required categories",
        ),
        metric_records.metric(
            "case_schema",
            "Case schema completeness",
            len(complete_cases) == len(cases),
            f"{len(complete_cases)}/{len(cases)}",
            "all cases include Sprint 14 fields",
        ),
        metric_records.metric(
            "demo_ready_cases",
            "Demo-ready cases",
            demo_ready_count >= 5,
            demo_ready_count,
            "5+",
        ),
        metric_records.metric(
            "required_sections",
            "Required output sections",
            required_sections == len(cases),
            f"{required_sections}/{len(cases)}",
            "each case has 4+ sections",
        ),
        metric_records.metric(
            "unacceptable_claims",
            "Unacceptable claim guards",
            safety_cases == len(cases),
            f"{safety_cases}/{len(cases)}",
            "each case defines unsafe/unacceptable claims",
        ),
        metric_records.metric(
            "next_actions",
            "Expected next action",
            next_actions == len(cases),
            f"{next_actions}/{len(cases)}",
            "each case defines expected next action type",
        ),
    ]
