#!/usr/bin/env python3
"""Run local AI quality gates and write JSON, Markdown, HTML, and trend reports."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import urllib.error
import urllib.request
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
API_DIR = ROOT / "apps" / "api"
DEFAULT_REPORT_DIR = ROOT / "reports" / "evals"
REPORT_DIR_ENV = "THESYS_EVAL_REPORT_DIR"

if str(API_DIR) not in sys.path:
    sys.path.insert(0, str(API_DIR))

from app.features.evals import (  # noqa: E402
    gate_results,
    langsmith_export,
    report_summary,
    report_writer,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Run Thesys AI quality gates.")
    parser.add_argument("--api-base", default="http://localhost:8000")
    parser.add_argument("--project-id", default=None)
    parser.add_argument("--skip-pytest", action="store_true")
    parser.add_argument("--skip-security", action="store_true")
    parser.add_argument("--strict-security-audit", action="store_true")
    parser.add_argument("--export-langsmith", action="store_true")
    parser.add_argument("--upload-langsmith", action="store_true")
    parser.add_argument("--json", action="store_true", dest="json_output")
    args = parser.parse_args()

    report_dir = _report_dir()
    report_dir.mkdir(parents=True, exist_ok=True)
    generated_at = datetime.now(UTC).replace(microsecond=0).isoformat()
    metadata = _metadata(args, generated_at)

    gates = [
        _run_json_gate(
            "ai_quality",
            [
                sys.executable,
                "scripts/eval_ai_quality.py",
                "--json",
                *(_project_args(args) if args.project_id else []),
            ],
            purpose="structured output, context, guide, redaction, cost, and AI accounting",
        ),
        _run_json_gate(
            "retrieval_quality",
            [sys.executable, "scripts/eval_retrieval_quality.py"],
            purpose="retrieval golden set, reranking, diversity, and citation support",
        ),
        _run_json_gate(
            "research_sprint_dataset",
            [
                sys.executable,
                "scripts/eval_research_sprints.py",
                "--json",
                *(_project_args(args) if args.project_id else []),
            ],
            purpose="agentic research dataset shape and safety expectations",
        ),
        _run_json_gate(
            "extraction_quality",
            [sys.executable, "scripts/eval_extraction_quality.py", "--json"],
            purpose="source ingestion, document extraction, provenance, and injection markers",
        ),
        _cache_quality_gate(),
    ]
    gates.append(_mcp_contract_gate(args))
    gates.append(_pytest_gate(args.skip_pytest))
    gates.append(_security_gate(args))

    summary = _summary(metadata, gates, live_snapshot=_live_project_snapshot(args))
    if args.export_langsmith or args.upload_langsmith:
        summary["langsmith_export"] = _export_langsmith(
            summary,
            report_dir,
            upload=args.upload_langsmith,
        )

    paths = _write_reports(summary, report_dir)
    summary["paths"] = paths
    if args.json_output:
        print(json.dumps(summary, indent=2, sort_keys=True))
    else:
        print(_render_text_summary(summary))
    return 0 if summary["passed"] else 1


def _report_dir() -> Path:
    configured = os.environ.get(REPORT_DIR_ENV)
    return Path(configured).expanduser() if configured else DEFAULT_REPORT_DIR


def _metadata(args: argparse.Namespace, generated_at: str) -> dict[str, Any]:
    return {
        "generated_at": generated_at,
        "sprint": "57",
        "git_commit": _git(["rev-parse", "--short", "HEAD"]),
        "git_branch": _git(["rev-parse", "--abbrev-ref", "HEAD"]),
        "provider_mode": "deterministic_or_configured",
        "model_mode": os.environ.get("LLM_STUB_MODE", "auto"),
        "prompt_version": "mixed; see persisted AI runs",
        "schema_version": "eval-quality-gate:v1",
        "context_profile_version": "context-pack:v1",
        "retrieval_policy_version": "retrieval-quality:v3",
        "memory_policy_version": "memory-manager:v2",
        "tool_schema_version": "thesys-mcp-adapter:v1",
        "api_base": args.api_base,
        "project_id": args.project_id,
    }


def _project_args(args: argparse.Namespace) -> list[str]:
    return ["--api-base", args.api_base, "--project-id", args.project_id]


def _run_json_gate(name: str, command: list[str], *, purpose: str) -> dict[str, Any]:
    result = subprocess.run(command, cwd=ROOT, text=True, capture_output=True, check=False)
    return gate_results.json_command_gate(
        name,
        command,
        purpose=purpose,
        returncode=result.returncode,
        stdout=result.stdout,
        stderr=result.stderr,
    )


def _cache_quality_gate() -> dict[str, Any]:
    cache_model_source = _read("apps/api/app/db/models/cache.py")
    cache_service_source = _read("apps/api/app/services/ai_cache_service.py")
    config_source = _read("apps/api/app/core/config.py")
    evidence_service_source = _read("apps/api/app/services/evidence_service.py")
    retrieval_service_source = _read("apps/api/app/services/retrieval_service.py")
    guide_service_source = _read("apps/api/app/services/guide_service.py")
    report_service_source = _read("apps/api/app/services/eval_report_service.py")
    observability_metrics_source = _read(
        "apps/api/app/features/evals/observability_metrics.py"
    )
    gate_source = _read("scripts/eval_quality_gate.py")
    checks = [
        (
            "cache_models_exist",
            "AICacheEntry" in cache_model_source and "AICacheEvent" in cache_model_source,
            "DB-backed cache entries and per-access events exist",
        ),
        (
            "cache_scoped_to_workspace_project",
            "workspace_id" in cache_service_source and "project_id" in cache_service_source,
            "cache keys/events are scoped by workspace and project",
        ),
        (
            "versioned_cache_keys",
            "project_state_versions" in cache_service_source
            and "version changed" in cache_service_source,
            "cache keys include project state versions and stale-denial reasons",
        ),
        (
            "embedding_cache_integration",
            "embed_text_with_metadata_cached" in evidence_service_source
            and "embed_text_with_metadata_cached" in retrieval_service_source,
            "chunk and query embeddings use the cache-aware embedding wrapper",
        ),
        (
            "retrieval_rerank_cache_integration",
            "cache_type=\"retrieval_plan\"" in retrieval_service_source
            and "cache_type=\"rerank_result\"" in retrieval_service_source,
            "retrieval plans and rerank results use cache entries",
        ),
        (
            "semantic_answer_cache_guarded",
            "ai_semantic_answer_cache_live_enabled" in config_source
            and "cache_type=\"guide_answer\"" in guide_service_source,
            "guide answer cache is optional and live-provider gated",
        ),
        (
            "cache_report_metrics",
            (
                "thesys.ai.cache.saved_tokens" in report_service_source
                or "thesys.ai.cache.saved_tokens" in observability_metrics_source
            )
            and "cache_quality" in gate_source,
            "cache hit/miss/stale/savings metrics reach reports and quality gates",
        ),
        (
            "cache_tests_exist",
            "test_ai_cache_service.py" in "\n".join(_repo_files("apps/api/app/tests")),
            "cache isolation and stale-denial tests exist",
        ),
    ]
    metrics = [
        {
            "key": key,
            "label": key.replace("_", " ").title(),
            "passed": passed,
            "observed": "present" if passed else "missing",
            "expected": expected,
        }
        for key, passed, expected in checks
    ]
    score = sum(1 for metric in metrics if metric["passed"])
    total = len(metrics)
    return {
        "name": "cache_quality",
        "purpose": "semantic caching, stale denial, isolation, and saved cost/latency reporting",
        "status": "pass" if score == total else "fail",
        "passed": score == total,
        "score": score,
        "total": total,
        "metrics": metrics,
        "command": [],
        "returncode": None,
        "stdout_tail": "",
        "stderr_tail": "",
        "rerun": "python3 scripts/eval_quality_gate.py --json",
    }


def _mcp_contract_gate(args: argparse.Namespace) -> dict[str, Any]:
    if not args.project_id:
        return _warning_gate(
            "mcp_contract",
            "MCP contract eval requires --project-id and a running API.",
            "python3 scripts/eval_quality_gate.py --project-id <id>",
        )
    return _run_json_gate(
        "mcp_contract",
        [
            sys.executable,
            "scripts/eval_mcp_contract.py",
            "--json",
            "--api-base",
            args.api_base,
            "--project-id",
            args.project_id,
        ],
        purpose="JSON-RPC initialize, tools/list, read tool, and proposal tool behavior",
    )


def _pytest_gate(skip: bool) -> dict[str, Any]:
    if skip:
        return _warning_gate(
            "pytest_quality_slice",
            "Pytest quality slice was skipped by --skip-pytest.",
            "cd apps/api && .venv/bin/pytest <quality slice> -q",
        )
    python = API_DIR / ".venv" / "bin" / "python"
    executable = str(python if python.exists() else Path(sys.executable))
    command = [
        executable,
        "-m",
        "pytest",
        "app/tests/test_ai.py",
        "app/tests/test_context_compiler.py",
        "app/tests/test_citation_verifier.py",
        "app/tests/test_retrieval_quality_eval.py",
        "app/tests/test_ai_cache_service.py",
        "app/tests/test_guide.py",
        "app/tests/test_evidence.py",
        "app/tests/test_langsmith_observability.py",
        "app/tests/test_mcp_adapter.py",
        "app/tests/test_security_governance.py",
        "-q",
    ]
    return _run_command_gate(
        "pytest_quality_slice",
        command,
        cwd=API_DIR,
        purpose=(
            "structured output, context, retrieval, cache, guide, extraction, redaction, "
            "MCP, security, and citation tests"
        ),
    )


def _security_gate(args: argparse.Namespace) -> dict[str, Any]:
    if args.skip_security:
        return _warning_gate(
            "security_check",
            "Security check was skipped by --skip-security.",
            "python3 scripts/security_check.py",
        )
    return _run_command_gate(
        "security_check",
        [
            sys.executable,
            "scripts/security_check.py",
            *(["--strict-audit"] if args.strict_security_audit else []),
        ],
        cwd=ROOT,
        purpose="security, egress, redaction, dependency-audit, MCP, and budget checks",
    )


def _run_command_gate(
    name: str,
    command: list[str],
    *,
    cwd: Path,
    purpose: str,
) -> dict[str, Any]:
    result = subprocess.run(command, cwd=cwd, text=True, capture_output=True, check=False)
    return gate_results.command_gate(
        name,
        command,
        purpose=purpose,
        returncode=result.returncode,
        stdout=result.stdout,
        stderr=result.stderr,
    )


_warning_gate = gate_results.warning_gate


def _summary(
    metadata: dict[str, Any],
    gates: list[dict[str, Any]],
    *,
    live_snapshot: dict[str, Any] | None,
) -> dict[str, Any]:
    return report_summary.summary(metadata, gates, live_snapshot=live_snapshot)


def _live_project_snapshot(args: argparse.Namespace) -> dict[str, Any] | None:
    if not args.project_id:
        return None
    ai_body = _fetch_json(f"{args.api_base.rstrip('/')}/api/projects/{args.project_id}/evals/ai")
    workflow_body = _fetch_json(
        f"{args.api_base.rstrip('/')}/api/projects/{args.project_id}/workflows"
    )
    observability_body = _fetch_json(
        f"{args.api_base.rstrip('/')}/api/projects/{args.project_id}/evals/observability-metrics"
    )
    runs = workflow_body.get("runs", []) if isinstance(workflow_body, dict) else []
    trace_ids = [
        str(run["langsmith_trace_id"])
        for run in runs
        if isinstance(run, dict) and run.get("langsmith_trace_id")
    ]
    return {
        "ai_report": ai_body.get("report", {}) if isinstance(ai_body, dict) else {},
        "observability": observability_body if isinstance(observability_body, dict) else {},
        "trace_ids": trace_ids[:20],
    }


def _cache_from_live_snapshot(live_snapshot: dict[str, Any] | None) -> dict[str, Any]:
    return report_summary.cache_from_live_snapshot(live_snapshot)


def _fetch_json(url: str) -> dict[str, Any]:
    request = urllib.request.Request(url, headers={"Accept": "application/json"})
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            return json.loads(response.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError):
        return {}


def _write_reports(summary: dict[str, Any], report_dir: Path) -> dict[str, Any]:
    return report_writer.write_reports(summary, report_dir, repo_root=ROOT)


def _trend_record(summary: dict[str, Any]) -> dict[str, Any]:
    return report_writer.trend_record(summary)


def _render_text_summary(summary: dict[str, Any]) -> str:
    return report_writer.render_text_summary(summary)


def _render_markdown(summary: dict[str, Any]) -> str:
    return report_writer.render_markdown(summary)


def _render_html(summary: dict[str, Any]) -> str:
    return report_writer.render_html(summary)


def _export_langsmith(
    summary: dict[str, Any],
    report_dir: Path,
    *,
    upload: bool,
) -> dict[str, Any]:
    payload = _redact(summary)
    export_path = langsmith_export.export_path(report_dir, summary)
    export_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    result = langsmith_export.export_result(export_path, repo_root=ROOT)
    if not upload:
        return result
    api_key = os.environ.get("LANGSMITH_API_KEY")
    if not api_key:
        return langsmith_export.export_result(
            export_path,
            repo_root=ROOT,
            status="warning",
            message="LANGSMITH_API_KEY is not configured.",
        )
    try:
        sys.path.insert(0, str(API_DIR))
        from langsmith import Client

        project_name = os.environ.get("LANGSMITH_PROJECT", "thesys-local")
        client = Client(api_key=api_key, api_url=os.environ.get("LANGSMITH_ENDPOINT"))
        client.create_run(
            name="thesys_eval_quality_gate",
            run_type="chain",
            inputs=langsmith_export.run_inputs(summary),
            outputs=payload,
            project_name=project_name,
        )
        return langsmith_export.export_result(
            export_path,
            repo_root=ROOT,
            uploaded=True,
            status="uploaded",
        )
    except Exception as exc:  # pragma: no cover - external telemetry is best-effort
        return langsmith_export.export_result(
            export_path,
            repo_root=ROOT,
            status="warning",
            message=str(exc),
        )


_redact = langsmith_export.redacted_export_payload


_parse_json_output = gate_results.parse_json_output


def as_dict(value: Any) -> dict[str, Any]:
    return report_summary.as_dict(value)


def _read(relative_path: str) -> str:
    path = ROOT / relative_path
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8")


def _repo_files(relative_path: str) -> list[str]:
    path = ROOT / relative_path
    if not path.exists():
        return []
    return [str(item.relative_to(ROOT)) for item in path.rglob("*") if item.is_file()]


def _git(args: list[str]) -> str:
    result = subprocess.run(["git", *args], cwd=ROOT, text=True, capture_output=True, check=False)
    return result.stdout.strip() if result.returncode == 0 else "unknown"


def _display_path(path: Path) -> str:
    return report_writer.display_path(path, repo_root=ROOT)


def _escape(value: Any) -> str:
    return report_writer.escape(value)


if __name__ == "__main__":
    raise SystemExit(main())
