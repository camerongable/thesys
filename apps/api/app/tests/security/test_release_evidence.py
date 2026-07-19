import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[5]
SCRIPT = REPO_ROOT / "scripts" / "prepare_release_evidence.py"


def test_release_evidence_collects_trivy_findings_and_named_signatures(tmp_path: Path) -> None:
    trivy = tmp_path / "trivy.json"
    trivy.write_text(
        json.dumps(
            {
                "Results": [
                    {
                        "Target": "thesys-api",
                        "Vulnerabilities": [
                            {
                                "VulnerabilityID": "CVE-2026-1",
                                "Severity": "HIGH",
                                "PkgName": "openssl",
                                "InstalledVersion": "3.0.0",
                            }
                        ],
                    }
                ]
            }
        )
    )
    output = tmp_path / "evidence.json"
    checks = (
        "tenant_isolation",
        "pii_leakage",
        "prompt_injection",
        "tool_policy",
        "memory_poisoning",
        "redteam",
        "dependency_scan",
        "container_scan",
    )

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--output",
            str(output),
            "--sbom-path",
            "artifacts/api.sbom.cdx.json",
            "--required-image",
            "api",
            "--required-image",
            "web",
            "--image-sbom",
            "api=artifacts/api.sbom.cdx.json",
            "--image-sbom",
            "web=artifacts/web.sbom.cdx.json",
            "--image-signature",
            "api=registry.example/api@sha256:" + "a" * 64,
            "--image-signature",
            "web=registry.example/web@sha256:" + "b" * 64,
            "--trivy-report",
            str(trivy),
            *[argument for check in checks for argument in ("--check", f"{check}=true")],
        ],
        check=False,
        text=True,
        capture_output=True,
    )

    assert result.returncode == 0, result.stderr
    evidence = json.loads(output.read_text())
    assert all(evidence["checks"].values())
    assert evidence["image_signatures"] == {
        "api": "registry.example/api@sha256:" + "a" * 64,
        "web": "registry.example/web@sha256:" + "b" * 64,
    }
    assert evidence["container_vulnerabilities"] == [
        {
            "id": "CVE-2026-1",
            "installed_version": "3.0.0",
            "package": "openssl",
            "severity": "HIGH",
            "target": "thesys-api",
        }
    ]
