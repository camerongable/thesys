import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[5]
SCRIPT = REPO_ROOT / "scripts" / "check_osv_pr_delta.py"


def _report(*findings: tuple[str, str, str, str]) -> dict[str, object]:
    packages = [
        {
            "package": {"ecosystem": ecosystem, "name": name, "version": version},
            "groups": [{"ids": [vulnerability_id]}],
        }
        for ecosystem, name, version, vulnerability_id in findings
    ]
    return {"results": [{"packages": packages}]}


def _run(baseline: Path, current: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), "--baseline", str(baseline), "--current", str(current)],
        text=True,
        capture_output=True,
        check=False,
    )


def test_osv_pr_delta_ignores_existing_findings(tmp_path: Path) -> None:
    finding = ("PyPI", "existing-package", "1.0.0", "GHSA-existing")
    baseline = tmp_path / "baseline.json"
    current = tmp_path / "current.json"
    baseline.write_text(json.dumps(_report(finding)), encoding="utf-8")
    current.write_text(json.dumps(_report(finding)), encoding="utf-8")

    result = _run(baseline, current)

    assert result.returncode == 0
    assert "No new OSV" in result.stdout


def test_osv_pr_delta_fails_for_new_findings(tmp_path: Path) -> None:
    baseline = tmp_path / "baseline.json"
    current = tmp_path / "current.json"
    baseline.write_text(json.dumps(_report()), encoding="utf-8")
    current.write_text(
        json.dumps(_report(("PyPI", "new-package", "2.0.0", "GHSA-new"))),
        encoding="utf-8",
    )

    result = _run(baseline, current)

    assert result.returncode == 1
    assert "PyPI:new-package@2.0.0: GHSA-new" in result.stdout
