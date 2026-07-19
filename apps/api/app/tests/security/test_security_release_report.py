import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[5]
REPORT_SCRIPT = REPO_ROOT / "scripts" / "generate_security_report.py"


def _evidence(sbom_path: Path, **overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "checks": {
            "tenant_isolation": True,
            "pii_leakage": True,
            "prompt_injection": True,
            "tool_policy": True,
            "memory_poisoning": True,
            "redteam": True,
            "dependency_scan": True,
            "container_scan": True,
        },
        "dependency_vulnerabilities": [],
        "container_vulnerabilities": [],
        "sbom_path": str(sbom_path),
        "image_signature": "cosign://registry.example/thesys@sha256:approved",
    }
    payload.update(overrides)
    return payload


def _run_report(evidence_path: Path, output_dir: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            sys.executable,
            str(REPORT_SCRIPT),
            "--evidence",
            str(evidence_path),
            "--output-dir",
            str(output_dir),
        ],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )


def test_security_release_report_allows_only_complete_evidence(tmp_path: Path) -> None:
    sbom_path = tmp_path / "sbom.cdx.json"
    sbom_path.write_text('{"bomFormat":"CycloneDX"}', encoding="utf-8")
    evidence_path = tmp_path / "evidence.json"
    evidence_path.write_text(json.dumps(_evidence(sbom_path)), encoding="utf-8")

    result = _run_report(evidence_path, tmp_path / "reports")

    assert result.returncode == 0, result.stderr
    report = json.loads((tmp_path / "reports" / "security-report.json").read_text())
    assert report["release_decision"] == "release"
    assert report["red_team"]["pass_rate"] == 1.0
    assert report["sbom_digest"].startswith("sha256:")
    assert report["model_versions"]
    assert report["prompt_versions"]
    assert "# Security Release Report" in (tmp_path / "reports" / "security-report.md").read_text()


def test_security_release_report_blocks_missing_or_failed_evidence(tmp_path: Path) -> None:
    evidence_path = tmp_path / "evidence.json"
    evidence_path.write_text(
        json.dumps(
            _evidence(
                tmp_path / "missing-sbom.json",
                checks={"prompt_injection": False},
                dependency_vulnerabilities=[{"id": "CVE-test", "severity": "critical"}],
                image_signature="",
            )
        ),
        encoding="utf-8",
    )

    result = _run_report(evidence_path, tmp_path / "reports")

    assert result.returncode == 1
    report = json.loads((tmp_path / "reports" / "security-report.json").read_text())
    assert report["release_decision"] == "blocked"
    assert {
        "prompt_injection",
        "sbom_missing",
        "image_unsigned",
        "high_or_critical_vulnerability",
    } <= set(report["blockers"])
