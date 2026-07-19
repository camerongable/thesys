#!/usr/bin/env python3
"""Build a fail-closed release security report from verified CI evidence."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[1]
API_DIR = ROOT / "apps" / "api"
REDTEAM_ROOT = ROOT / "security" / "redteam"
REQUIRED_CHECKS = (
    "tenant_isolation",
    "pii_leakage",
    "prompt_injection",
    "tool_policy",
    "memory_poisoning",
    "redteam",
    "dependency_scan",
    "container_scan",
)

if str(API_DIR) not in sys.path:
    sys.path.insert(0, str(API_DIR))

from app.security.model_registry import APPROVED_MODELS  # noqa: E402
from app.security.prompt_registry import (  # noqa: E402
    APPROVED_PROMPT_VERSIONS,
    active_prompt_contents,
    ensure_approved_prompt_version,
)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Generate a fail-closed security release report."
    )
    parser.add_argument("--evidence", type=Path, required=True)
    parser.add_argument(
        "--output-dir", type=Path, default=ROOT / "reports" / "security"
    )
    args = parser.parse_args()

    evidence = _load_evidence(args.evidence)
    report = _build_report(evidence)
    _write_reports(report, args.output_dir)
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["release_decision"] == "release" else 1


def _load_evidence(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("Security release evidence must be a JSON object.")
    return payload


def _build_report(evidence: dict[str, Any]) -> dict[str, Any]:
    checks = _check_results(evidence)
    registry = _registry_inventory()
    sbom_path = _optional_path(evidence.get("sbom_path"))
    signature = _optional_text(evidence.get("image_signature"))
    dependency_vulnerabilities = _list_value(evidence.get("dependency_vulnerabilities"))
    container_vulnerabilities = _list_value(evidence.get("container_vulnerabilities"))
    blockers = _blockers(
        checks=checks,
        registry=registry,
        sbom_path=sbom_path,
        image_signature=signature,
        dependency_vulnerabilities=dependency_vulnerabilities,
        container_vulnerabilities=container_vulnerabilities,
    )
    return {
        "generated_at": datetime.now(UTC).replace(microsecond=0).isoformat(),
        "git_commit": _git("rev-parse", "--short", "HEAD"),
        "owasp_genai_control_coverage": {
            "prompt_injection": checks["prompt_injection"],
            "data_leakage": checks["pii_leakage"],
            "insecure_tool_use": checks["tool_policy"],
            "memory_poisoning": checks["memory_poisoning"],
            "supply_chain": checks["dependency_scan"] and checks["container_scan"],
        },
        "red_team": _red_team_summary(checks["redteam"]),
        "unresolved_high_critical_findings": _high_critical_findings(
            dependency_vulnerabilities + container_vulnerabilities
        ),
        "dependency_vulnerabilities": dependency_vulnerabilities,
        "container_vulnerabilities": container_vulnerabilities,
        "tenant_isolation_result": _result(checks["tenant_isolation"]),
        "pii_leakage_result": _result(checks["pii_leakage"]),
        "prompt_injection_result": _result(checks["prompt_injection"]),
        "tool_policy_result": _result(checks["tool_policy"]),
        "memory_poisoning_result": _result(checks["memory_poisoning"]),
        "model_versions": registry["models"],
        "prompt_versions": registry["prompts"],
        "sbom_digest": _file_digest(sbom_path),
        "image_signature": signature,
        "release_gates": checks,
        "release_decision": "release" if not blockers else "blocked",
        "blockers": blockers,
    }


def _check_results(evidence: dict[str, Any]) -> dict[str, bool]:
    evidence_checks = evidence.get("checks")
    if not isinstance(evidence_checks, dict):
        evidence_checks = {}
    return {
        **{name: evidence_checks.get(name) is True for name in REQUIRED_CHECKS},
        "model_registry": _registry_inventory()["models_valid"],
        "prompt_registry": _registry_inventory()["prompts_valid"],
    }


def _registry_inventory() -> dict[str, Any]:
    prompt_contents = active_prompt_contents()
    try:
        for prompt_version in prompt_contents:
            ensure_approved_prompt_version(prompt_version)
    except ValueError:
        prompts_valid = False
    else:
        prompts_valid = bool(APPROVED_PROMPT_VERSIONS)
    enabled_models = [model for model in APPROVED_MODELS if model.enabled]
    return {
        "models_valid": bool(enabled_models),
        "prompts_valid": prompts_valid,
        "models": [
            {
                "provider": model.provider,
                "model_id": model.model_id,
                "purpose": model.purpose,
                "security_eval_version": model.security_eval_version,
            }
            for model in enabled_models
        ],
        "prompts": sorted(prompt_contents),
    }


def _red_team_summary(passed: bool) -> dict[str, Any]:
    suites = []
    cases = 0
    for path in sorted(REDTEAM_ROOT.glob("*.yaml")):
        document = yaml.safe_load(path.read_text(encoding="utf-8"))
        if not isinstance(document, dict) or "cases" not in document:
            continue
        suites.append(document["suite"])
        cases += len(document["cases"])
    return {
        "passed": passed,
        "pass_rate": 1.0 if passed else 0.0,
        "suites": suites,
        "cases": cases,
    }


def _blockers(
    *,
    checks: dict[str, bool],
    registry: dict[str, Any],
    sbom_path: Path | None,
    image_signature: str | None,
    dependency_vulnerabilities: list[dict[str, Any]],
    container_vulnerabilities: list[dict[str, Any]],
) -> list[str]:
    blockers = [name for name, passed in checks.items() if not passed]
    if not registry["models_valid"]:
        blockers.append("model_registry")
    if not registry["prompts_valid"]:
        blockers.append("prompt_registry")
    if sbom_path is None:
        blockers.append("sbom_missing")
    if image_signature is None:
        blockers.append("image_unsigned")
    if _high_critical_findings(dependency_vulnerabilities + container_vulnerabilities):
        blockers.append("high_or_critical_vulnerability")
    return sorted(set(blockers))


def _high_critical_findings(findings: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        finding
        for finding in findings
        if str(finding.get("severity", "")).casefold() in {"high", "critical"}
    ]


def _optional_path(value: Any) -> Path | None:
    if not isinstance(value, str) or not value.strip():
        return None
    path = Path(value)
    return path if path.is_file() else None


def _optional_text(value: Any) -> str | None:
    return value.strip() if isinstance(value, str) and value.strip() else None


def _list_value(value: Any) -> list[dict[str, Any]]:
    return (
        value
        if isinstance(value, list) and all(isinstance(item, dict) for item in value)
        else []
    )


def _file_digest(path: Path | None) -> str | None:
    if path is None:
        return None
    return f"sha256:{hashlib.sha256(path.read_bytes()).hexdigest()}"


def _result(passed: bool) -> str:
    return "pass" if passed else "fail"


def _write_reports(report: dict[str, Any], output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "security-report.json").write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    (output_dir / "security-report.md").write_text(
        _render_markdown(report), encoding="utf-8"
    )


def _render_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# Security Release Report",
        "",
        f"- Generated: `{report['generated_at']}`",
        f"- Commit: `{report['git_commit']}`",
        f"- Release decision: `{report['release_decision']}`",
        f"- SBOM digest: `{report['sbom_digest'] or 'missing'}`",
        f"- Image signature: `{report['image_signature'] or 'missing'}`",
        "",
        "## Release Gates",
        "",
    ]
    lines.extend(
        f"- `{name}`: `{'pass' if passed else 'fail'}`"
        for name, passed in report["release_gates"].items()
    )
    lines.extend(
        [
            "",
            "## Security Results",
            "",
            f"- Red-team pass rate: `{report['red_team']['pass_rate']:.0%}`",
            f"- Red-team cases: `{report['red_team']['cases']}`",
            f"- High/critical findings: `{len(report['unresolved_high_critical_findings'])}`",
            f"- Approved model records: `{len(report['model_versions'])}`",
            f"- Approved prompt versions: `{len(report['prompt_versions'])}`",
            "",
            "## Blockers",
            "",
        ]
    )
    lines.extend(f"- `{blocker}`" for blocker in report["blockers"] or ["none"])
    return "\n".join(lines) + "\n"


def _git(*args: str) -> str:
    result = subprocess.run(
        ["git", *args], cwd=ROOT, text=True, capture_output=True, check=False
    )
    return result.stdout.strip() or "unknown"


if __name__ == "__main__":
    raise SystemExit(main())
