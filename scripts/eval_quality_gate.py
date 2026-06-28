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
        "sprint": "56",
        "git_commit": _git(["rev-parse", "--short", "HEAD"]),
        "git_branch": _git(["rev-parse", "--abbrev-ref", "HEAD"]),
        "provider_mode": "deterministic_or_configured",
        "model_mode": os.environ.get("LLM_STUB_MODE", "auto"),
        "prompt_version": "mixed; see persisted AI runs",
        "schema_version": "eval-quality-gate:v1",
        "context_profile_version": "context-pack:v1",
        "retrieval_policy_version": "retrieval-quality:v2",
        "memory_policy_version": "memory-manager:v2",
        "tool_schema_version": "thesys-mcp-adapter:v1",
        "api_base": args.api_base,
        "project_id": args.project_id,
    }


def _project_args(args: argparse.Namespace) -> list[str]:
    return ["--api-base", args.api_base, "--project-id", args.project_id]


def _run_json_gate(name: str, command: list[str], *, purpose: str) -> dict[str, Any]:
    result = subprocess.run(command, cwd=ROOT, text=True, capture_output=True, check=False)
    parsed = _parse_json_output(result.stdout)
    status = "pass" if result.returncode == 0 and bool(parsed.get("passed")) else "fail"
    return {
        "name": name,
        "purpose": purpose,
        "status": status,
        "passed": status == "pass",
        "score": int(parsed.get("score") or (1 if status == "pass" else 0)),
        "total": int(parsed.get("total") or 1),
        "metrics": parsed.get("metrics") or [],
        "command": command,
        "returncode": result.returncode,
        "stdout_tail": result.stdout[-2500:],
        "stderr_tail": result.stderr[-2500:],
        "rerun": " ".join(command),
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
            "structured output, context, retrieval, guide, extraction, redaction, MCP, "
            "security, and citation tests"
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
    status = "pass" if result.returncode == 0 else "fail"
    return {
        "name": name,
        "purpose": purpose,
        "status": status,
        "passed": status == "pass",
        "score": 1 if status == "pass" else 0,
        "total": 1,
        "metrics": [
            {
                "key": name,
                "label": name.replace("_", " ").title(),
                "passed": status == "pass",
                "observed": f"exit {result.returncode}",
                "expected": "exit 0",
            }
        ],
        "command": command,
        "returncode": result.returncode,
        "stdout_tail": result.stdout[-2500:],
        "stderr_tail": result.stderr[-2500:],
        "rerun": " ".join(command),
    }


def _warning_gate(name: str, message: str, rerun: str) -> dict[str, Any]:
    return {
        "name": name,
        "purpose": message,
        "status": "warn",
        "passed": True,
        "score": 0,
        "total": 0,
        "metrics": [
            {
                "key": f"{name}_unavailable",
                "label": name.replace("_", " ").title(),
                "passed": True,
                "observed": "unavailable",
                "expected": message,
            }
        ],
        "command": [],
        "returncode": None,
        "stdout_tail": "",
        "stderr_tail": "",
        "rerun": rerun,
    }


def _summary(
    metadata: dict[str, Any],
    gates: list[dict[str, Any]],
    *,
    live_snapshot: dict[str, Any] | None,
) -> dict[str, Any]:
    failed = [gate for gate in gates if gate["status"] == "fail"]
    warnings = [gate for gate in gates if gate["status"] == "warn"]
    score = sum(int(gate.get("score") or 0) for gate in gates)
    total = sum(int(gate.get("total") or 0) for gate in gates)
    failed_check_ids = [
        metric.get("key", gate["name"])
        for gate in gates
        for metric in gate.get("metrics", [])
        if not metric.get("passed", False)
    ]
    live_ai_report = as_dict(live_snapshot.get("ai_report")) if live_snapshot else {}
    return {
        **metadata,
        "available": True,
        "passed": not failed,
        "status": "pass" if not failed and not warnings else ("fail" if failed else "warn"),
        "score": score,
        "total": total,
        "failed_check_ids": failed_check_ids,
        "warning_gate_ids": [gate["name"] for gate in warnings],
        "gates": gates,
        "reports": gates,
        "cache": {"hits": 0, "misses": 0, "stale_denials": 0},
        "latency_ms": live_ai_report.get("average_step_latency_ms"),
        "token_cost": {
            "total_tokens": live_ai_report.get("total_tokens"),
            "total_cost": live_ai_report.get("total_cost"),
        },
        "trace_ids": live_snapshot.get("trace_ids", []) if live_snapshot else [],
        "changelog": "docs/AI_CHANGELOG.md",
    }


def _live_project_snapshot(args: argparse.Namespace) -> dict[str, Any] | None:
    if not args.project_id:
        return None
    ai_body = _fetch_json(f"{args.api_base.rstrip('/')}/api/projects/{args.project_id}/evals/ai")
    workflow_body = _fetch_json(
        f"{args.api_base.rstrip('/')}/api/projects/{args.project_id}/workflows"
    )
    runs = workflow_body.get("runs", []) if isinstance(workflow_body, dict) else []
    trace_ids = [
        str(run["langsmith_trace_id"])
        for run in runs
        if isinstance(run, dict) and run.get("langsmith_trace_id")
    ]
    return {
        "ai_report": ai_body.get("report", {}) if isinstance(ai_body, dict) else {},
        "trace_ids": trace_ids[:20],
    }


def _fetch_json(url: str) -> dict[str, Any]:
    request = urllib.request.Request(url, headers={"Accept": "application/json"})
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            return json.loads(response.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError):
        return {}


def _write_reports(summary: dict[str, Any], report_dir: Path) -> dict[str, str]:
    stamp = summary["generated_at"].replace(":", "").replace("+00:00", "Z")
    stem = f"eval_report_{stamp}"
    json_path = report_dir / f"{stem}.json"
    markdown_path = report_dir / f"{stem}.md"
    html_path = report_dir / f"{stem}.html"
    latest_json = report_dir / "latest.json"
    latest_md = report_dir / "latest.md"
    latest_html = report_dir / "latest.html"
    trend_path = report_dir / "eval_runs.jsonl"

    json_body = json.dumps(summary, indent=2, sort_keys=True)
    markdown_body = _render_markdown(summary)
    html_body = _render_html(summary)
    json_path.write_text(json_body, encoding="utf-8")
    markdown_path.write_text(markdown_body, encoding="utf-8")
    html_path.write_text(html_body, encoding="utf-8")
    latest_json.write_text(json_body, encoding="utf-8")
    latest_md.write_text(markdown_body, encoding="utf-8")
    latest_html.write_text(html_body, encoding="utf-8")
    with trend_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(_trend_record(summary), sort_keys=True) + "\n")

    return {
        "json": _display_path(json_path),
        "markdown": _display_path(markdown_path),
        "html": _display_path(html_path),
        "latest_json": _display_path(latest_json),
        "latest_markdown": _display_path(latest_md),
        "latest_html": _display_path(latest_html),
        "trends": _display_path(trend_path),
    }


def _trend_record(summary: dict[str, Any]) -> dict[str, Any]:
    return {
        "generated_at": summary["generated_at"],
        "sprint": summary["sprint"],
        "git_commit": summary["git_commit"],
        "git_branch": summary["git_branch"],
        "passed": summary["passed"],
        "status": summary["status"],
        "score": summary["score"],
        "total": summary["total"],
        "prompt_version": summary["prompt_version"],
        "schema_version": summary["schema_version"],
        "context_profile_version": summary["context_profile_version"],
        "retrieval_policy_version": summary["retrieval_policy_version"],
        "memory_policy_version": summary["memory_policy_version"],
        "model_mode": summary["model_mode"],
        "provider_mode": summary["provider_mode"],
        "failed_check_ids": summary["failed_check_ids"],
        "warning_gate_ids": summary["warning_gate_ids"],
        "gates": [
            {
                "name": gate["name"],
                "status": gate["status"],
                "score": gate["score"],
                "total": gate["total"],
            }
            for gate in summary["gates"]
        ],
    }


def _render_text_summary(summary: dict[str, Any]) -> str:
    lines = [
        "Thesys Eval Quality Gate",
        f"Result: {summary['status']} ({summary['score']}/{summary['total']})",
    ]
    for gate in summary["gates"]:
        lines.append(
            f"- [{gate['status'].upper()}] {gate['name']}: "
            f"{gate['score']}/{gate['total']}"
        )
    lines.append(f"Report: {summary['paths']['latest_markdown']}")
    return "\n".join(lines)


def _render_markdown(summary: dict[str, Any]) -> str:
    lines = [
        "# Thesys Eval Report",
        "",
        f"- Generated: `{summary['generated_at']}`",
        f"- Sprint: `{summary['sprint']}`",
        f"- Commit: `{summary['git_commit']}`",
        f"- Result: `{summary['status']}`",
        f"- Score: `{summary['score']}/{summary['total']}`",
        "",
        "## Gates",
        "",
    ]
    for gate in summary["gates"]:
        lines.append(f"### {gate['name']}")
        lines.append("")
        lines.append(f"- Status: `{gate['status']}`")
        lines.append(f"- Score: `{gate['score']}/{gate['total']}`")
        lines.append(f"- Purpose: {gate['purpose']}")
        lines.append(f"- Rerun: `{gate['rerun']}`")
        failed = [metric for metric in gate.get("metrics", []) if not metric.get("passed", False)]
        if failed:
            lines.append("- Failing cases:")
            for metric in failed:
                lines.append(
                    f"  - `{metric.get('key', gate['name'])}`: observed "
                    f"`{metric.get('observed')}`, expected `{metric.get('expected')}`"
                )
        lines.append("")
    lines.extend(
        [
            "## Versions",
            "",
            f"- Prompt version: `{summary['prompt_version']}`",
            f"- Schema version: `{summary['schema_version']}`",
            f"- Context profile version: `{summary['context_profile_version']}`",
            f"- Retrieval policy version: `{summary['retrieval_policy_version']}`",
            f"- Memory policy version: `{summary['memory_policy_version']}`",
            f"- Tool schema version: `{summary['tool_schema_version']}`",
            "",
            "## Changelog",
            "",
            "See `docs/AI_CHANGELOG.md`.",
        ]
    )
    return "\n".join(lines) + "\n"


def _render_html(summary: dict[str, Any]) -> str:
    rows = "\n".join(
        "<tr>"
        f"<td>{_escape(gate['name'])}</td>"
        f"<td>{_escape(gate['status'].upper())}</td>"
        f"<td>{gate['score']}/{gate['total']}</td>"
        f"<td><code>{_escape(gate['rerun'])}</code></td>"
        "</tr>"
        for gate in summary["gates"]
    )
    return f"""<!doctype html>
<html>
<head><meta charset="utf-8"><title>Thesys Eval Report</title></head>
<body>
<h1>Thesys Eval Report</h1>
<p>Generated: {_escape(summary['generated_at'])}</p>
<p>Result: {_escape(summary['status'])} ({summary['score']}/{summary['total']})</p>
<table border="1" cellspacing="0" cellpadding="6">
<tr><th>Gate</th><th>Status</th><th>Score</th><th>Rerun</th></tr>
{rows}
</table>
<p>Changelog: docs/AI_CHANGELOG.md</p>
</body>
</html>
"""


def _export_langsmith(
    summary: dict[str, Any],
    report_dir: Path,
    *,
    upload: bool,
) -> dict[str, Any]:
    payload = _redact(summary)
    export_path = report_dir / f"langsmith_export_{summary['generated_at'].replace(':', '')}.json"
    export_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    result = {
        "path": _display_path(export_path),
        "uploaded": False,
        "status": "exported",
    }
    if not upload:
        return result
    api_key = os.environ.get("LANGSMITH_API_KEY")
    if not api_key:
        return {**result, "status": "warning", "message": "LANGSMITH_API_KEY is not configured."}
    try:
        sys.path.insert(0, str(API_DIR))
        from langsmith import Client

        project_name = os.environ.get("LANGSMITH_PROJECT", "thesys-local")
        client = Client(api_key=api_key, api_url=os.environ.get("LANGSMITH_ENDPOINT"))
        client.create_run(
            name="thesys_eval_quality_gate",
            run_type="chain",
            inputs={"sprint": summary["sprint"], "git_commit": summary["git_commit"]},
            outputs=payload,
            project_name=project_name,
        )
        return {**result, "uploaded": True, "status": "uploaded"}
    except Exception as exc:  # pragma: no cover - external telemetry is best-effort
        return {**result, "status": "warning", "message": str(exc)}


def _redact(value: Any) -> Any:
    sys.path.insert(0, str(API_DIR))
    from app.core.redaction import redact_payload

    return redact_payload(value, redact_emails=True, max_string_length=2000)


def _parse_json_output(stdout: str) -> dict[str, Any]:
    try:
        return json.loads(stdout)
    except json.JSONDecodeError:
        start = stdout.find("{")
        end = stdout.rfind("}")
        if start >= 0 and end > start:
            try:
                return json.loads(stdout[start : end + 1])
            except json.JSONDecodeError:
                pass
    return {"passed": False, "score": 0, "total": 1, "metrics": []}


def as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _git(args: list[str]) -> str:
    result = subprocess.run(["git", *args], cwd=ROOT, text=True, capture_output=True, check=False)
    return result.stdout.strip() if result.returncode == 0 else "unknown"


def _display_path(path: Path) -> str:
    return str(path.relative_to(ROOT)) if path.is_relative_to(ROOT) else str(path)


def _escape(value: Any) -> str:
    return (
        str(value)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


if __name__ == "__main__":
    raise SystemExit(main())
