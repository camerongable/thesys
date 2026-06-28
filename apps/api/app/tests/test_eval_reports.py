import json
import os
import subprocess
import sys
from pathlib import Path

from fastapi.testclient import TestClient


def test_eval_report_endpoints_read_file_backed_reports(
    client: TestClient,
    monkeypatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("THESYS_EVAL_REPORT_DIR", str(tmp_path))
    latest = {
        "available": True,
        "status": "warn",
        "score": 2,
        "total": 3,
        "gates": [{"name": "context", "status": "pass", "score": 1, "total": 1}],
        "paths": {"latest_json": "reports/evals/latest.json"},
    }
    (tmp_path / "latest.json").write_text(json.dumps(latest), encoding="utf-8")
    (tmp_path / "eval_runs.jsonl").write_text(
        "\n".join(
            [
                json.dumps({"generated_at": "2026-01-01T00:00:00Z", "status": "pass"}),
                json.dumps({"generated_at": "2026-01-02T00:00:00Z", "status": "warn"}),
            ]
        ),
        encoding="utf-8",
    )
    project_id = client.post("/api/projects", json={"name": "Eval report project"}).json()["id"]

    latest_response = client.get(f"/api/projects/{project_id}/evals/reports/latest")
    trend_response = client.get(f"/api/projects/{project_id}/evals/reports/trends?limit=1")

    assert latest_response.status_code == 200
    assert latest_response.json()["report"]["status"] == "warn"
    assert trend_response.status_code == 200
    trends = trend_response.json()["trends"]
    assert len(trends) == 1
    assert trends[0]["status"] == "warn"


def test_eval_observability_metrics_endpoint_reports_project_metrics(
    client: TestClient,
    monkeypatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("THESYS_EVAL_REPORT_DIR", str(tmp_path))
    (tmp_path / "latest.json").write_text(
        json.dumps({"available": True, "cache": {"hits": 2, "misses": 1, "stale_denials": 0}}),
        encoding="utf-8",
    )
    project_id = client.post("/api/projects", json={"name": "Eval metrics project"}).json()["id"]

    response = client.get(f"/api/projects/{project_id}/evals/observability-metrics")

    assert response.status_code == 200
    body = response.json()
    names = {metric["name"] for metric in body["metrics"]}
    assert {
        "thesys.ai.workflow.runs",
        "thesys.ai.tokens.total",
        "thesys.ai.cost.total",
        "thesys.ai.cache.hits",
        "thesys.provider_egress.policy.enabled",
    } <= names
    cache_hits = next(
        metric for metric in body["metrics"] if metric["name"] == "thesys.ai.cache.hits"
    )
    assert cache_hits["value"] == 2
    assert cache_hits["temporality"] == "cumulative"


def test_eval_quality_gate_script_writes_reports(tmp_path: Path) -> None:
    repo_root = Path(__file__).resolve().parents[4]
    env = {
        **os.environ,
        "THESYS_EVAL_REPORT_DIR": str(tmp_path),
        "LLM_STUB_MODE": "always",
    }

    result = subprocess.run(
        [
            sys.executable,
            str(repo_root / "scripts/eval_quality_gate.py"),
            "--json",
            "--skip-pytest",
            "--skip-security",
        ],
        cwd=repo_root,
        check=False,
        capture_output=True,
        text=True,
        env=env,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    body = json.loads(result.stdout)
    assert body["passed"] is True
    assert body["status"] == "warn"
    assert "mcp_contract" in body["warning_gate_ids"]
    assert (tmp_path / "latest.json").exists()
    assert (tmp_path / "latest.md").exists()
    assert (tmp_path / "latest.html").exists()
    assert (tmp_path / "eval_runs.jsonl").exists()
