import json
import os
import subprocess
import sys
from pathlib import Path

from fastapi.testclient import TestClient

from app.features.evals import (
    gate_results,
    langsmith_export,
    metric_records,
    observability_metrics,
    provider_warnings,
    report_failures,
    report_summary,
    report_writer,
)
from app.schemas.evals import (
    EvalCacheDiagnosticRead,
    EvalExportResultRead,
    EvalGateMetricRecord,
    EvalGateResultRead,
    EvalMetricPointRead,
    EvalReportFailureRead,
    EvalReportSummaryRead,
)
from app.services import eval_report_service


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


def test_eval_report_endpoints_surface_missing_and_malformed_reports(
    client: TestClient,
    monkeypatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("THESYS_EVAL_REPORT_DIR", str(tmp_path))
    project_id = client.post("/api/projects", json={"name": "Malformed eval project"}).json()["id"]

    missing_response = client.get(f"/api/projects/{project_id}/evals/reports/latest")

    assert missing_response.status_code == 200
    missing_report = missing_response.json()["report"]
    assert missing_report["available"] is False
    assert missing_report["status"] == "unavailable"
    assert "eval_quality_gate.py" in missing_report["message"]

    (tmp_path / "latest.json").write_text("{not-json", encoding="utf-8")
    (tmp_path / "eval_runs.jsonl").write_text(
        "\n".join(
            [
                json.dumps({"generated_at": "2026-01-01T00:00:00Z", "status": "pass"}),
                "{bad trend json",
            ]
        ),
        encoding="utf-8",
    )

    malformed_response = client.get(f"/api/projects/{project_id}/evals/reports/latest")
    trend_response = client.get(f"/api/projects/{project_id}/evals/reports/trends?limit=2")

    assert malformed_response.status_code == 200
    malformed_report = malformed_response.json()["report"]
    assert malformed_report["available"] is False
    assert malformed_report["status"] == "warning"
    assert "not valid JSON" in malformed_report["message"]
    assert trend_response.status_code == 200
    trends = trend_response.json()["trends"]
    assert trends[0]["status"] == "pass"
    assert trends[1]["status"] == "warning"
    assert "malformed trend record" in trends[1]["message"]


def test_eval_report_failure_helpers_shape_safe_warning_payloads(tmp_path: Path) -> None:
    missing = report_failures.missing_report()
    malformed = report_failures.malformed_report(tmp_path / "latest.json")
    unreadable = report_failures.unreadable_report(
        tmp_path / "latest.json",
        PermissionError("denied"),
    )
    trend = report_failures.unreadable_trend_file(
        tmp_path / "eval_runs.jsonl",
        PermissionError("denied"),
    )

    assert missing["status"] == "unavailable"
    assert "eval_quality_gate.py" in missing["message"]
    assert malformed == {
        "available": False,
        "status": "warning",
        "message": f"Eval report is not valid JSON: {tmp_path / 'latest.json'}",
    }
    assert unreadable["available"] is False
    assert unreadable["status"] == "warning"
    assert "PermissionError" in unreadable["message"]
    assert report_failures.malformed_trend_record()["status"] == "warning"
    assert trend["status"] == "warning"
    assert "PermissionError" in trend["message"]
    unwritable = report_failures.unwritable_trend_file(
        tmp_path / "eval_runs.jsonl",
        PermissionError("read-only"),
    )
    assert unwritable["status"] == "warning"
    assert "could not be written" in unwritable["message"]
    assert "PermissionError" in unwritable["message"]


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


def test_eval_observability_metrics_prefers_persisted_cache_over_report_cache(
    client: TestClient,
    monkeypatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("THESYS_EVAL_REPORT_DIR", str(tmp_path))
    (tmp_path / "latest.json").write_text(
        json.dumps({"available": True, "cache": {"hits": 99, "misses": 99}}),
        encoding="utf-8",
    )
    monkeypatch.setattr(
        eval_report_service.ai_cache_service,
        "cache_summary",
        lambda *args, **kwargs: {
            "hits": 3,
            "misses": 4,
            "stale_denials": 1,
            "saved_tokens": 12,
            "saved_cost": 0.25,
            "latency_saved_ms": 42,
        },
    )
    project_id = client.post(
        "/api/projects",
        json={"name": "Persisted cache metric project"},
    ).json()["id"]

    response = client.get(f"/api/projects/{project_id}/evals/observability-metrics")

    assert response.status_code == 200
    metrics = {metric["name"]: metric for metric in response.json()["metrics"]}
    assert metrics["thesys.ai.cache.hits"]["value"] == 3
    assert metrics["thesys.ai.cache.misses"]["value"] == 4
    assert metrics["thesys.ai.cache.stale_denials"]["value"] == 1
    assert metrics["thesys.ai.cache.saved_tokens"]["value"] == 12
    assert metrics["thesys.ai.cache.saved_cost"]["value"] == 0.25
    assert metrics["thesys.ai.cache.latency_saved"]["value"] == 42


def test_eval_report_writer_creates_reports_latest_aliases_and_trend(tmp_path: Path) -> None:
    summary = {
        "generated_at": "2026-01-02T03:04:05+00:00",
        "sprint": "59",
        "git_commit": "abc123",
        "git_branch": "codex/v1-sprints-51-60",
        "passed": False,
        "status": "warn",
        "score": 1,
        "total": 2,
        "prompt_version": "prompt:v1",
        "schema_version": "schema:v1",
        "context_profile_version": "context:v1",
        "retrieval_policy_version": "retrieval:v1",
        "memory_policy_version": "memory:v1",
        "model_mode": "always",
        "provider_mode": "deterministic",
        "tool_schema_version": "tools:v1",
        "failed_check_ids": ["unsafe_html"],
        "warning_gate_ids": ["mcp_contract"],
        "paths": {"latest_markdown": "reports/evals/latest.md"},
        "gates": [
            {
                "name": "unsafe<html>",
                "purpose": "escape unsafe report values",
                "status": "fail",
                "passed": False,
                "score": 0,
                "total": 1,
                "rerun": "python <unsafe>",
                "metrics": [
                    {
                        "key": "unsafe_html",
                        "passed": False,
                        "observed": "<script>",
                        "expected": "escaped",
                    }
                ],
            },
            {
                "name": "context",
                "purpose": "context quality",
                "status": "pass",
                "passed": True,
                "score": 1,
                "total": 1,
                "rerun": "python context",
                "metrics": [],
            },
        ],
    }

    paths = report_writer.write_reports(summary, tmp_path, repo_root=tmp_path)

    assert Path(paths["latest_json"]).name == "latest.json"
    assert (tmp_path / "latest.json").exists()
    assert (tmp_path / "latest.md").exists()
    assert (tmp_path / "latest.html").exists()
    assert (tmp_path / "eval_report_2026-01-02T030405+0000.json").exists()
    assert (tmp_path / "eval_report_2026-01-02T030405+0000.md").exists()
    assert (tmp_path / "eval_report_2026-01-02T030405+0000.html").exists()
    trend_records = (tmp_path / "eval_runs.jsonl").read_text(encoding="utf-8").splitlines()
    assert len(trend_records) == 1
    trend = json.loads(trend_records[0])
    assert trend["failed_check_ids"] == ["unsafe_html"]
    assert trend["gates"][0] == {
        "name": "unsafe<html>",
        "status": "fail",
        "score": 0,
        "total": 1,
    }

    markdown = (tmp_path / "latest.md").read_text(encoding="utf-8")
    assert "unsafe_html" in markdown
    assert "observed `<script>`, expected `escaped`" in markdown

    html = (tmp_path / "latest.html").read_text(encoding="utf-8")
    assert "unsafe&lt;html&gt;" in html
    assert "python &lt;unsafe&gt;" in html

    summary["paths"] = paths
    assert report_writer.render_text_summary(summary).endswith("Report: latest.md")


def test_eval_report_writer_surfaces_trend_write_failure(
    monkeypatch,
    tmp_path: Path,
) -> None:
    summary = {
        "generated_at": "2026-01-02T03:04:05+00:00",
        "sprint": "59",
        "git_commit": "abc123",
        "git_branch": "codex/v1-sprints-51-60",
        "passed": True,
        "status": "pass",
        "score": 1,
        "total": 1,
        "prompt_version": "prompt:v1",
        "schema_version": "schema:v1",
        "context_profile_version": "context:v1",
        "retrieval_policy_version": "retrieval:v1",
        "memory_policy_version": "memory:v1",
        "model_mode": "always",
        "provider_mode": "deterministic",
        "tool_schema_version": "tools:v1",
        "failed_check_ids": [],
        "warning_gate_ids": [],
        "paths": {"latest_markdown": "reports/evals/latest.md"},
        "gates": [
            {
                "name": "context",
                "purpose": "context quality",
                "status": "pass",
                "passed": True,
                "score": 1,
                "total": 1,
                "rerun": "python context",
                "metrics": [],
            }
        ],
    }

    def fail_append(_trend_path: Path, _summary: dict[str, object]) -> None:
        raise PermissionError("trend directory is read-only")

    monkeypatch.setattr(report_writer, "append_trend_record", fail_append)

    paths = report_writer.write_reports(summary, tmp_path, repo_root=tmp_path)

    assert (tmp_path / "latest.json").exists()
    assert (tmp_path / "latest.md").exists()
    assert (tmp_path / "latest.html").exists()
    assert paths["trend_write"]["status"] == "warning"
    assert "Eval trend file could not be written" in paths["trend_write"]["message"]
    assert "PermissionError" in paths["trend_write"]["message"]
    assert not (tmp_path / "eval_runs.jsonl").exists()


def test_eval_report_summary_shapes_status_failures_and_live_cache() -> None:
    metadata = {
        "generated_at": "2026-01-02T03:04:05+00:00",
        "sprint": "59",
        "git_commit": "abc123",
        "git_branch": "codex/v1-sprints-51-60",
        "prompt_version": "prompt:v1",
        "schema_version": "schema:v1",
        "context_profile_version": "context:v1",
        "retrieval_policy_version": "retrieval:v1",
        "memory_policy_version": "memory:v1",
        "model_mode": "always",
        "provider_mode": "deterministic",
        "tool_schema_version": "tools:v1",
    }
    gates = [
        {
            "name": "context",
            "status": "pass",
            "score": 2,
            "total": 2,
            "metrics": [{"key": "context_ok", "passed": True}],
        },
        {
            "name": "provider",
            "status": "warn",
            "score": 0,
            "total": 0,
            "metrics": [{"key": "provider_unavailable", "passed": True}],
        },
        {
            "name": "retrieval",
            "status": "fail",
            "score": 1,
            "total": 2,
            "metrics": [{"key": "recall_at_k", "passed": False}],
        },
    ]
    live_snapshot = {
        "ai_report": {
            "average_step_latency_ms": 125,
            "total_tokens": 345,
            "total_cost": "0.42",
        },
        "trace_ids": ["trace-1"],
        "observability": {
            "metrics": [
                {"name": "thesys.ai.cache.hits", "value": "4"},
                {"name": "thesys.ai.cache.misses", "value": 2.8},
                {"name": "thesys.ai.cache.stale_denials", "value": 1},
                {"name": "thesys.ai.cache.saved_tokens", "value": 99},
                {"name": "thesys.ai.cache.saved_cost", "value": "1.25"},
                {"name": "thesys.ai.cache.latency_saved", "value": 88},
            ]
        },
    }

    summary = report_summary.summary(metadata, gates, live_snapshot=live_snapshot)
    validated_summary = EvalReportSummaryRead.model_validate(summary)

    assert summary["available"] is True
    assert summary["passed"] is False
    assert summary["status"] == "fail"
    assert summary["score"] == 3
    assert summary["total"] == 4
    assert summary["failed_check_ids"] == ["recall_at_k"]
    assert summary["warning_gate_ids"] == ["provider"]
    assert summary["reports"] == gates
    assert summary["latency_ms"] == 125
    assert summary["token_cost"] == {"total_tokens": 345, "total_cost": "0.42"}
    assert summary["trace_ids"] == ["trace-1"]
    assert summary["cache"] == {
        "hits": 4,
        "misses": 2,
        "stale_denials": 1,
        "saved_tokens": 99,
        "saved_cost": "1.25",
        "latency_saved_ms": 88,
    }
    assert validated_summary.cache.saved_tokens == 99
    assert validated_summary.token_cost.total_cost == "0.42"
    assert report_summary.cache_from_live_snapshot(None)["hits"] == 0


def test_eval_report_summary_falls_back_to_gate_id_for_partial_failures() -> None:
    gates = [
        {
            "name": "security_check",
            "status": "fail",
            "passed": False,
            "score": 0,
            "total": 1,
            "metrics": [],
        },
        {
            "name": "retrieval_quality",
            "status": "fail",
            "passed": False,
            "score": 0,
            "total": 1,
            "metrics": [{"key": "setup_completed", "passed": True}],
        },
        {
            "name": "guide_eval",
            "status": "fail",
            "passed": False,
            "score": 1,
            "total": 2,
            "metrics": [{"key": "citation_validity", "passed": False}],
        },
    ]

    summary = report_summary.summary({}, gates, live_snapshot=None)

    assert summary["failed_check_ids"] == [
        "security_check",
        "retrieval_quality",
        "citation_validity",
    ]


def test_eval_gate_result_helpers_parse_and_shape_command_results() -> None:
    stdout = 'prefix\n{"passed": true, "score": 2, "total": 3, "metrics": [{"key": "ok"}]}\n'

    parsed = gate_results.parse_json_output(stdout)
    json_gate = gate_results.json_command_gate(
        "sample_gate",
        ["python", "sample.py"],
        purpose="sample purpose",
        returncode=0,
        stdout=stdout,
        stderr="",
    )
    failed_gate = gate_results.json_command_gate(
        "sample_gate",
        ["python", "sample.py"],
        purpose="sample purpose",
        returncode=1,
        stdout='{"passed": true, "score": 2, "total": 3, "metrics": []}',
        stderr="failed",
    )
    command_gate = gate_results.command_gate(
        "plain_gate",
        ["python", "plain.py"],
        purpose="plain purpose",
        returncode=2,
        stdout="o" * 2600,
        stderr="e" * 2600,
    )

    assert parsed["score"] == 2
    assert gate_results.parse_json_output("not-json") == {
        "passed": False,
        "score": 0,
        "total": 1,
        "metrics": [],
    }
    assert json_gate == {
        "name": "sample_gate",
        "purpose": "sample purpose",
        "status": "pass",
        "passed": True,
        "score": 2,
        "total": 3,
        "metrics": [{"key": "ok"}],
        "command": ["python", "sample.py"],
        "returncode": 0,
        "stdout_tail": stdout[-2500:],
        "stderr_tail": "",
        "rerun": "python sample.py",
    }
    assert failed_gate["status"] == "fail"
    assert failed_gate["passed"] is False
    assert failed_gate["score"] == 2
    assert command_gate["status"] == "fail"
    assert command_gate["metrics"] == [
        {
            "key": "plain_gate",
            "label": "Plain Gate",
            "passed": False,
            "observed": "exit 2",
            "expected": "exit 0",
        }
    ]
    assert len(command_gate["stdout_tail"]) == 2500
    assert len(command_gate["stderr_tail"]) == 2500


def test_eval_metric_record_helper_shapes_optional_warnings() -> None:
    assert metric_records.metric(
        "source_quality",
        "Source quality",
        True,
        {"risk": "low"},
        "low risk",
    ) == {
        "key": "source_quality",
        "label": "Source quality",
        "passed": True,
        "observed": {"risk": "low"},
        "expected": "low risk",
    }
    assert metric_records.metric(
        "live_provider",
        "Live provider",
        True,
        "unavailable",
        "visible warning",
        warnings=["TAVILY_API_KEY missing"],
    ) == {
        "key": "live_provider",
        "label": "Live provider",
        "passed": True,
        "observed": "unavailable",
        "expected": "visible warning",
        "warnings": ["TAVILY_API_KEY missing"],
    }


def test_eval_helpers_validate_typed_dto_boundaries(tmp_path: Path) -> None:
    gate = gate_results.warning_gate(
        "mcp_contract",
        "MCP contract eval requires --project-id and a running API.",
        "python3 scripts/eval_quality_gate.py --project-id <id>",
    )
    metric = metric_records.metric(
        "live_provider",
        "Live provider",
        True,
        "unavailable",
        "visible warning",
        warnings=["TAVILY_API_KEY missing"],
    )
    failure = report_failures.missing_report()
    cache = report_summary.cache_from_live_snapshot(None)
    summary = report_summary.summary(
        {"generated_at": "2026-01-02T03:04:05+00:00"},
        [gate],
        live_snapshot=None,
    )
    export = langsmith_export.export_result(
        tmp_path / "langsmith_export_2026-01-02T030405+0000.json",
        repo_root=tmp_path,
        status="warning",
        message="LANGSMITH_API_KEY is not configured.",
    )
    otel_metric = observability_metrics.metric(
        "thesys.ai.workflow.runs",
        1,
        "1",
        {"source": "local"},
    )

    assert EvalGateResultRead.model_validate(gate).status == "warn"
    assert EvalGateMetricRecord.model_validate(metric).warnings == [
        "TAVILY_API_KEY missing"
    ]
    assert EvalReportFailureRead.model_validate(failure).available is False
    assert EvalCacheDiagnosticRead.model_validate(cache).saved_cost == "0"
    assert EvalReportSummaryRead.model_validate(summary).status == "warn"
    assert EvalExportResultRead.model_validate(export).message == (
        "LANGSMITH_API_KEY is not configured."
    )
    assert EvalMetricPointRead.model_validate(otel_metric).temporality == "cumulative"


def test_eval_provider_warning_helper_shapes_live_provider_metric() -> None:
    metric = provider_warnings.live_provider_unavailable_metric(
        multimodal_provider="deterministic",
        litellm_key_configured=True,
        tavily_key_configured=False,
    )

    assert metric["key"] == "live_provider_unavailable_warning"
    assert metric["passed"] is True
    assert metric["observed"] == {
        "multimodal_provider": "deterministic",
        "litellm_key_configured": True,
        "tavily_key_configured": False,
        "warning_count": 2,
    }
    assert metric["warnings"] == [
        "Tavily live source QA skipped: TAVILY_API_KEY missing; "
        "rerun with search credentials and egress allowlist",
        "multimodal live provider skipped: provider is deterministic; "
        "set MULTIMODAL_EXTRACTION_PROVIDER=litellm for live QA",
    ]
    assert provider_warnings.live_provider_warning_messages(
        multimodal_provider="litellm",
        litellm_key_configured=False,
        tavily_key_configured=True,
    ) == [
        "multimodal live provider skipped: LITELLM_API_KEY missing; "
        "rerun with provider credentials and egress allowlist"
    ]


def test_eval_langsmith_export_helpers_redact_payload_and_shape_status(tmp_path: Path) -> None:
    summary = {
        "generated_at": "2026-01-02T03:04:05+00:00",
        "sprint": "Sprint 59",
        "git_commit": "abc123",
        "contact": "founder@example.com",
        "api_key": "sk-test-secret-123456789",
        "total_tokens": 42,
    }

    payload = langsmith_export.redacted_export_payload(summary)
    export_path = langsmith_export.export_path(tmp_path, summary)
    result = langsmith_export.export_result(export_path, repo_root=tmp_path)

    assert payload["contact"] == "[redacted-email]"
    assert payload["api_key"] == "[redacted]"
    assert payload["total_tokens"] == 42
    assert langsmith_export.export_filename(summary["generated_at"]) == (
        "langsmith_export_2026-01-02T030405+0000.json"
    )
    assert export_path == tmp_path / "langsmith_export_2026-01-02T030405+0000.json"
    assert result == {"path": export_path.name, "uploaded": False, "status": "exported"}
    assert langsmith_export.export_result(
        export_path,
        repo_root=tmp_path,
        uploaded=True,
        status="uploaded",
    ) == {"path": export_path.name, "uploaded": True, "status": "uploaded"}
    assert langsmith_export.export_result(
        export_path,
        repo_root=tmp_path,
        status="warning",
        message="LANGSMITH_API_KEY is not configured.",
    ) == {
        "path": export_path.name,
        "uploaded": False,
        "status": "warning",
        "message": "LANGSMITH_API_KEY is not configured.",
    }
    assert langsmith_export.run_inputs(summary) == {
        "sprint": "Sprint 59",
        "git_commit": "abc123",
    }


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
    assert {
        "mcp_contract",
        "pytest_quality_slice",
        "security_check",
    }.issubset(set(body["warning_gate_ids"]))
    warning_gates = {gate["name"]: gate for gate in body["gates"] if gate["status"] == "warn"}
    assert warning_gates["security_check"] == gate_results.warning_gate(
        "security_check",
        "Security check was skipped by --skip-security.",
        "python3 scripts/security_check.py",
    )
    assert "paths" in body
    assert (tmp_path / "latest.json").exists()
    assert (tmp_path / "latest.md").exists()
    assert (tmp_path / "latest.html").exists()
    assert (tmp_path / "eval_runs.jsonl").exists()
    latest = json.loads((tmp_path / "latest.json").read_text(encoding="utf-8"))
    assert "paths" not in latest


def test_eval_quality_gate_script_exports_langsmith_payload_without_upload(
    tmp_path: Path,
) -> None:
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
            "--export-langsmith",
        ],
        cwd=repo_root,
        check=False,
        capture_output=True,
        text=True,
        env=env,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    body = json.loads(result.stdout)
    export_result = body["langsmith_export"]
    export_path = Path(export_result["path"])
    if not export_path.is_absolute():
        export_path = repo_root / export_path

    assert export_result["uploaded"] is False
    assert export_result["status"] == "exported"
    assert export_path.exists()
    payload = json.loads(export_path.read_text(encoding="utf-8"))
    assert payload["sprint"] == body["sprint"]
    assert payload["git_commit"] == body["git_commit"]
    assert "paths" not in payload
