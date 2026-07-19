#!/usr/bin/env python3
"""Normalize release workflow outputs for the fail-closed security report."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

CHECKS = (
    "tenant_isolation",
    "pii_leakage",
    "prompt_injection",
    "tool_policy",
    "memory_poisoning",
    "redteam",
    "dependency_scan",
    "container_scan",
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Build release-report evidence from CI artifacts.")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--sbom-path")
    parser.add_argument("--image-sbom", action="append", default=[])
    parser.add_argument("--check", action="append", default=[])
    parser.add_argument("--required-image", action="append", default=[])
    parser.add_argument("--image-signature", action="append", default=[])
    parser.add_argument("--trivy-report", action="append", default=[])
    args = parser.parse_args()

    checks = {name: False for name in CHECKS}
    for value in args.check:
        name, passed = _split_assignment(value, "check")
        if name not in checks:
            raise ValueError(f"Unknown release check: {name}")
        checks[name] = _as_bool(passed)

    signatures = dict(
        assignment
        for value in args.image_signature
        if (assignment := _split_optional_assignment(value, "image signature")) is not None
    )
    sbom_paths = dict(
        assignment
        for value in args.image_sbom
        if (assignment := _split_optional_assignment(value, "image SBOM")) is not None
    )
    evidence = {
        "checks": checks,
        "sbom_path": args.sbom_path,
        "sbom_paths": sbom_paths,
        "required_images": sorted(set(args.required_image)),
        "image_signatures": signatures,
        "dependency_vulnerabilities": [],
        "container_vulnerabilities": _trivy_findings(args.trivy_report),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(evidence, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return 0


def _split_assignment(value: str, label: str) -> tuple[str, str]:
    name, separator, assigned = value.partition("=")
    if not name or not separator or not assigned:
        raise ValueError(f"Expected {label} in NAME=VALUE form.")
    return name, assigned


def _split_optional_assignment(value: str, label: str) -> tuple[str, str] | None:
    name, separator, assigned = value.partition("=")
    if not name or not separator:
        raise ValueError(f"Expected {label} in NAME=VALUE form.")
    return (name, assigned) if assigned else None


def _as_bool(value: str) -> bool:
    if value == "true":
        return True
    if value == "false":
        return False
    raise ValueError("Release check values must be true or false.")


def _trivy_findings(paths: list[str]) -> list[dict[str, str]]:
    findings: list[dict[str, str]] = []
    for raw_path in paths:
        path = Path(raw_path)
        if not path.is_file():
            continue
        payload = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            continue
        for result in payload.get("Results", []):
            if not isinstance(result, dict):
                continue
            for vulnerability in result.get("Vulnerabilities") or []:
                if not isinstance(vulnerability, dict):
                    continue
                findings.append(_finding(vulnerability, result))
    return findings


def _finding(vulnerability: dict[str, Any], result: dict[str, Any]) -> dict[str, str]:
    return {
        "id": str(vulnerability.get("VulnerabilityID", "unknown")),
        "severity": str(vulnerability.get("Severity", "unknown")),
        "package": str(vulnerability.get("PkgName", "unknown")),
        "installed_version": str(vulnerability.get("InstalledVersion", "unknown")),
        "target": str(result.get("Target", "unknown")),
    }


if __name__ == "__main__":
    raise SystemExit(main())
