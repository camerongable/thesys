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
API_DIR = REPO_ROOT / "apps" / "api"

if str(API_DIR) not in sys.path:
    sys.path.insert(0, str(API_DIR))

from app.features.evals import metric_records, research_cases  # noqa: E402

DATASET_PATH = research_cases.dataset_path()
REQUIRED_CATEGORIES = research_cases.REQUIRED_CATEGORIES
REQUIRED_CASE_FIELDS = research_cases.REQUIRED_CASE_FIELDS


def main() -> int:
    parser = argparse.ArgumentParser(description="Evaluate research sprint readiness.")
    parser.add_argument("--api-base", default="http://localhost:8000")
    parser.add_argument("--project-id", default=None)
    parser.add_argument("--json", action="store_true", dest="json_output")
    args = parser.parse_args()

    cases = _load_cases()
    dataset_metrics = _score_dataset(cases)
    live_metrics: list[dict[str, Any]] = []
    if args.project_id:
        live_metrics = _fetch_project_metrics(args.api_base, args.project_id)

    metrics = [*dataset_metrics, *live_metrics]
    passed = sum(1 for metric in metrics if metric["passed"])
    total = len(metrics)

    report = {"passed": passed == total, "score": passed, "total": total, "metrics": metrics}
    if args.json_output:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        print("Research Sprint Eval")
        print(f"Dataset: {DATASET_PATH}")
        print(f"Result: {passed}/{total} checks passed")
        for metric in metrics:
            status = "PASS" if metric["passed"] else "FAIL"
            print(
                f"- [{status}] {metric['label']}: {metric['observed']} "
                f"(expected {metric['expected']})"
            )

    return 0 if report["passed"] else 1


def _load_cases() -> list[dict[str, Any]]:
    return research_cases.load_raw_cases(DATASET_PATH)


_score_dataset = research_cases.score_dataset


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


_metric = metric_records.metric


if __name__ == "__main__":
    sys.exit(main())
