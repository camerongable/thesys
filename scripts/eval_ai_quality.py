#!/usr/bin/env python3
"""Run local AI quality, safety, and cost eval gates.

The static checks work without a running API. Pass --project-id to include live
project AI accounting and Ask Thesys guide eval metrics.
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

from app.features.evals import metric_records  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Evaluate AI quality gates.")
    parser.add_argument("--api-base", default="http://localhost:8000")
    parser.add_argument("--project-id", default=None)
    parser.add_argument("--json", action="store_true", dest="json_output")
    args = parser.parse_args()

    metrics = _static_metrics()
    if args.project_id:
        metrics.extend(_fetch_project_eval(args.api_base, args.project_id, "ai"))
        metrics.extend(_fetch_project_eval(args.api_base, args.project_id, "guide"))
        metrics.extend(_fetch_project_eval(args.api_base, args.project_id, "context"))

    passed = sum(1 for metric in metrics if metric["passed"])
    total = len(metrics)
    report = {"passed": passed == total, "score": passed, "total": total, "metrics": metrics}
    if args.json_output:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        print("AI Eval Gate")
        print(f"Result: {passed}/{total} checks passed")
        for metric in metrics:
            status = "PASS" if metric["passed"] else "FAIL"
            print(
                f"- [{status}] {metric['label']}: {metric['observed']} "
                f"(expected {metric['expected']})"
            )
    return 0 if passed == total else 1


def _static_metrics() -> list[dict[str, Any]]:
    return [
        _metric(
            "context_service",
            "Context pack service",
            (REPO_ROOT / "apps/api/app/services/context_service.py").exists(),
            "present",
            "context pack builder exists",
        ),
        _metric(
            "citation_verifier",
            "Citation verifier",
            (
                REPO_ROOT / "apps/api/app/features/evidence/citation_verifier.py"
            ).exists(),
            "present",
            "shared citation verifier exists",
        ),
        _metric(
            "memory_service",
            "Memory service",
            (REPO_ROOT / "apps/api/app/services/memory_service.py").exists(),
            "present",
            "typed memory manager exists",
        ),
        _metric(
            "security_tests",
            "AI security tests",
            _contains(
                "apps/api/app/tests/test_security_governance.py",
                "evidence_url_fetch_blocked",
            )
            and _contains("apps/api/app/core/security.py", "validate_url_fetch_target"),
            "present",
            "security fixtures and URL fetch guard exist",
        ),
        _metric(
            "guide_eval_endpoint",
            "Guide eval endpoint",
            _contains("apps/api/app/routers/evals.py", "/guide"),
            "present",
            "guide eval route exists",
        ),
        _metric(
            "context_eval_endpoint",
            "Context eval endpoint",
            _contains("apps/api/app/routers/evals.py", "/context")
            and _contains("apps/api/app/services/eval_service.py", "run_context_eval"),
            "present",
            "context eval route exists",
        ),
        _metric(
            "ai_accounting",
            "AI accounting service",
            (REPO_ROOT / "apps/api/app/services/ai_accounting_service.py").exists(),
            "present",
            "cost and latency accounting exists",
        ),
        _metric(
            "source_provenance",
            "Source provenance service",
            (
                REPO_ROOT / "apps/api/app/features/evidence/source_provenance.py"
            ).exists()
            and _contains("apps/api/app/services/evidence_service.py", "content_hash"),
            "present",
            "canonical URL, hash, and provenance helpers exist",
        ),
        _metric(
            "prompt_injection_markers",
            "Fetched-page prompt injection markers",
            _contains(
                "apps/api/app/features/evidence/source_provenance.py",
                "PROMPT_INJECTION_PATTERNS",
            )
            and _contains("apps/api/app/tests/test_evidence.py", "prompt_injection_markers"),
            "present",
            "fetched-page prompt-injection detection is tested",
        ),
        _metric(
            "multimodal_lineage",
            "Multimodal extraction lineage",
            _contains("apps/api/app/features/evidence/extraction.py", "pdf_page_lineage")
            and _contains(
                "apps/api/app/features/evidence/source_provenance.py",
                "def pdf_page_lineage",
            )
            and _contains("apps/api/app/tests/test_evidence.py", "pdf_page_lineage"),
            "present",
            "PDF page lineage is recorded and tested",
        ),
    ]


def _fetch_project_eval(api_base: str, project_id: str, eval_name: str) -> list[dict[str, Any]]:
    url = f"{api_base.rstrip('/')}/api/projects/{project_id}/evals/{eval_name}"
    request = urllib.request.Request(url, headers={"Accept": "application/json"})
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            body = json.loads(response.read().decode("utf-8"))
    except urllib.error.URLError as exc:
        return [
            _metric(
                f"live_{eval_name}_eval",
                f"Live {eval_name} eval",
                False,
                str(exc),
                f"reachable /evals/{eval_name} endpoint",
            )
        ]
    return [
        _metric(
            f"live_{eval_name}_{metric['key']}",
            f"Live {eval_name}: {metric['label']}",
            bool(metric["passed"]),
            metric.get("observed"),
            metric.get("expected") or "pass",
        )
        for metric in body.get("metrics", [])
    ]


def _contains(relative_path: str, needle: str) -> bool:
    path = REPO_ROOT / relative_path
    return path.exists() and needle in path.read_text(encoding="utf-8")


_metric = metric_records.metric


if __name__ == "__main__":
    sys.exit(main())
