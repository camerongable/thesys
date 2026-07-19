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
        "image_signature": "registry.example/thesys@sha256:" + "a" * 64,
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
    assert report["sbom_digests"]["release"].startswith("sha256:")
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


def test_security_release_report_requires_a_signature_for_every_named_image(tmp_path: Path) -> None:
    sbom_path = tmp_path / "sbom.cdx.json"
    sbom_path.write_text('{"bomFormat":"CycloneDX"}', encoding="utf-8")
    evidence_path = tmp_path / "evidence.json"
    evidence_path.write_text(
        json.dumps(
            _evidence(
                sbom_path,
                image_signatures={"api": "registry.example/api@sha256:" + "a" * 64},
                required_images=["api", "web"],
            )
        ),
        encoding="utf-8",
    )

    result = _run_report(evidence_path, tmp_path / "reports")

    assert result.returncode == 1
    report = json.loads((tmp_path / "reports" / "security-report.json").read_text())
    assert report["image_signatures"] == {"api": "registry.example/api@sha256:" + "a" * 64}
    assert "image_unsigned" in report["blockers"]


def test_security_release_report_accepts_complete_named_artifact_evidence(tmp_path: Path) -> None:
    api_sbom = tmp_path / "api.sbom.cdx.json"
    web_sbom = tmp_path / "web.sbom.cdx.json"
    api_sbom.write_text('{"bomFormat":"CycloneDX","component":{"name":"api"}}')
    web_sbom.write_text('{"bomFormat":"CycloneDX","component":{"name":"web"}}')
    evidence_path = tmp_path / "evidence.json"
    evidence_path.write_text(
        json.dumps(
            _evidence(
                api_sbom,
                sbom_paths={"api": str(api_sbom), "web": str(web_sbom)},
                image_signatures={
                    "api": "registry.example/api@sha256:" + "a" * 64,
                    "web": "registry.example/web@sha256:" + "b" * 64,
                },
                required_images=["api", "web"],
            )
        ),
        encoding="utf-8",
    )

    result = _run_report(evidence_path, tmp_path / "reports")

    assert result.returncode == 0, result.stderr
    report = json.loads((tmp_path / "reports" / "security-report.json").read_text())
    assert set(report["sbom_digests"]) == {"api", "web"}
    assert set(report["image_signatures"]) == {"api", "web"}
