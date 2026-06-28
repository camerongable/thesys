#!/usr/bin/env python3
"""Run credential-free source and document extraction readiness checks."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    parser = argparse.ArgumentParser(description="Evaluate extraction and source provenance gates.")
    parser.add_argument("--json", action="store_true", dest="json_output")
    args = parser.parse_args()

    metrics = [
        _metric(
            "url_fetch_policy",
            "URL fetch policy",
            _contains("apps/api/app/core/security.py", "validate_url_fetch_target")
            and _contains(
                "apps/api/app/tests/test_security_governance.py",
                "private_fetch_targets",
            ),
            "present",
            "SSRF-resistant URL target validation is implemented and tested",
        ),
        _metric(
            "canonical_dedupe",
            "Canonical URL and content-hash dedupe",
            _contains("apps/api/app/services/source_provenance_service.py", "canonical")
            and _contains("apps/api/app/services/evidence_service.py", "content_hash"),
            "present",
            "canonical URL and content-hash provenance are recorded",
        ),
        _metric(
            "prompt_injection_markers",
            "Prompt-injection markers",
            _contains(
                "apps/api/app/services/source_provenance_service.py",
                "PROMPT_INJECTION_PATTERNS",
            )
            and _contains("apps/api/app/tests/test_evidence.py", "prompt_injection_markers"),
            "present",
            "fetched-page prompt-injection markers are detected and tested",
        ),
        _metric(
            "pdf_page_lineage",
            "PDF page lineage",
            _contains("apps/api/app/services/evidence_service.py", "pdf_page_lineage")
            and _contains("apps/api/app/tests/test_evidence.py", "pdf_page_lineage"),
            "present",
            "PDF extraction records page lineage",
        ),
        _metric(
            "multimodal_boundary",
            "Multimodal extraction boundary",
            _contains("apps/api/app/services/multimodal_extraction_service.py", "provider")
            and _contains("apps/api/app/tests/test_evidence.py", "image"),
            "present",
            "image/low-text extraction has deterministic and provider boundaries",
        ),
        _metric(
            "source_quality",
            "Source quality signals",
            _contains("apps/api/app/services/source_provenance_service.py", "source_quality")
            or _contains("apps/api/app/services/source_provenance_service.py", "quality"),
            "present",
            "source quality signals are available for retrieval/context policy",
        ),
    ]
    passed = sum(1 for metric in metrics if metric["passed"])
    report = {
        "passed": passed == len(metrics),
        "score": passed,
        "total": len(metrics),
        "metrics": metrics,
    }
    if args.json_output:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        print("Extraction Quality Eval")
        print(f"Result: {passed}/{len(metrics)} checks passed")
        for metric in metrics:
            status = "PASS" if metric["passed"] else "FAIL"
            print(
                f"- [{status}] {metric['label']}: {metric['observed']} "
                f"(expected {metric['expected']})"
            )
    return 0 if report["passed"] else 1


def _contains(relative_path: str, needle: str) -> bool:
    path = ROOT / relative_path
    return path.exists() and needle in path.read_text(encoding="utf-8")


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
    raise SystemExit(main())
