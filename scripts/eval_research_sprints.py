#!/usr/bin/env python3
"""Run local research sprint eval checks.

This command intentionally works without a running API by validating the seeded
eval dataset. If a project ID is provided, it also fetches the live project V1
research eval endpoint and folds those metrics into the summary.
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
DATASET_PATH = REPO_ROOT / "apps/api/app/evals/research_sprint_cases.json"
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


def main() -> int:
    parser = argparse.ArgumentParser(description="Evaluate research sprint readiness.")
    parser.add_argument("--api-base", default="http://localhost:8000")
    parser.add_argument("--project-id", default=None)
    args = parser.parse_args()

    cases = _load_cases()
    dataset_metrics = _score_dataset(cases)
    live_metrics: list[dict[str, Any]] = []
    if args.project_id:
        live_metrics = _fetch_project_metrics(args.api_base, args.project_id)

    metrics = [*dataset_metrics, *live_metrics]
    passed = sum(1 for metric in metrics if metric["passed"])
    total = len(metrics)

    print("Research Sprint Eval")
    print(f"Dataset: {DATASET_PATH}")
    print(f"Result: {passed}/{total} checks passed")
    for metric in metrics:
        status = "PASS" if metric["passed"] else "FAIL"
        print(f"- [{status}] {metric['label']}: {metric['observed']} (expected {metric['expected']})")

    return 0 if passed == total else 1


def _load_cases() -> list[dict[str, Any]]:
    return json.loads(DATASET_PATH.read_text(encoding="utf-8"))


def _score_dataset(cases: list[dict[str, Any]]) -> list[dict[str, Any]]:
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
        _metric("dataset_case_count", "Dataset case count", len(cases) >= 10, len(cases), "10+"),
        _metric(
            "category_coverage",
            "Category coverage",
            REQUIRED_CATEGORIES.issubset(categories),
            f"{len(categories)}/{len(REQUIRED_CATEGORIES)}",
            "all required categories",
        ),
        _metric(
            "case_schema",
            "Case schema completeness",
            len(complete_cases) == len(cases),
            f"{len(complete_cases)}/{len(cases)}",
            "all cases include Sprint 14 fields",
        ),
        _metric(
            "demo_ready_cases",
            "Demo-ready cases",
            demo_ready_count >= 5,
            demo_ready_count,
            "5+",
        ),
        _metric(
            "required_sections",
            "Required output sections",
            required_sections == len(cases),
            f"{required_sections}/{len(cases)}",
            "each case has 4+ sections",
        ),
        _metric(
            "unacceptable_claims",
            "Unacceptable claim guards",
            safety_cases == len(cases),
            f"{safety_cases}/{len(cases)}",
            "each case defines unsafe/unacceptable claims",
        ),
        _metric(
            "next_actions",
            "Expected next action",
            next_actions == len(cases),
            f"{next_actions}/{len(cases)}",
            "each case defines expected next action type",
        ),
    ]


def _fetch_project_metrics(api_base: str, project_id: str) -> list[dict[str, Any]]:
    url = f"{api_base.rstrip('/')}/api/projects/{project_id}/evals/v1-research"
    request = urllib.request.Request(url, headers={"Accept": "application/json"})
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            body = json.loads(response.read().decode("utf-8"))
    except urllib.error.URLError as exc:
        return [
            _metric(
                "live_project_eval",
                "Live project eval",
                False,
                str(exc),
                "reachable V1 research eval endpoint",
            )
        ]
    return [
        _metric(
            f"live_{metric['key']}",
            f"Live: {metric['label']}",
            bool(metric["passed"]),
            metric.get("observed"),
            metric.get("expected") or "pass",
        )
        for metric in body.get("metrics", [])
    ]


def _metric(
    key: str,
    label: str,
    passed: bool,
    observed: Any,
    expected: str,
) -> dict[str, Any]:
    return {
        "key": key,
        "label": label,
        "passed": passed,
        "observed": observed,
        "expected": expected,
    }


if __name__ == "__main__":
    sys.exit(main())
