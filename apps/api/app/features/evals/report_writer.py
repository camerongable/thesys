"""File-backed eval report writers and renderers for local quality gates."""

import json
from pathlib import Path
from typing import Any

from app.features.evals import report_failures

REPO_ROOT = Path(__file__).resolve().parents[5]


def write_reports(
    summary: dict[str, Any],
    report_dir: Path,
    *,
    repo_root: Path = REPO_ROOT,
) -> dict[str, Any]:
    """Write timestamped, latest, and trend eval report artifacts."""

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
    markdown_body = render_markdown(summary)
    html_body = render_html(summary)
    json_path.write_text(json_body, encoding="utf-8")
    markdown_path.write_text(markdown_body, encoding="utf-8")
    html_path.write_text(html_body, encoding="utf-8")
    latest_json.write_text(json_body, encoding="utf-8")
    latest_md.write_text(markdown_body, encoding="utf-8")
    latest_html.write_text(html_body, encoding="utf-8")
    paths: dict[str, Any] = {
        "json": display_path(json_path, repo_root=repo_root),
        "markdown": display_path(markdown_path, repo_root=repo_root),
        "html": display_path(html_path, repo_root=repo_root),
        "latest_json": display_path(latest_json, repo_root=repo_root),
        "latest_markdown": display_path(latest_md, repo_root=repo_root),
        "latest_html": display_path(latest_html, repo_root=repo_root),
        "trends": display_path(trend_path, repo_root=repo_root),
    }
    try:
        append_trend_record(trend_path, summary)
    except OSError as exc:
        paths["trend_write"] = report_failures.unwritable_trend_file(trend_path, exc)
    return paths


def append_trend_record(trend_path: Path, summary: dict[str, Any]) -> None:
    """Append one trend record for an eval summary."""

    with trend_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(trend_record(summary), sort_keys=True) + "\n")


def trend_record(summary: dict[str, Any]) -> dict[str, Any]:
    """Project a full eval summary into one append-only trend record."""

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


def render_text_summary(summary: dict[str, Any]) -> str:
    """Render the terminal-facing quality gate summary."""

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


def render_markdown(summary: dict[str, Any]) -> str:
    """Render the Markdown eval report used by local review and CI artifacts."""

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
        failed = [
            metric for metric in gate.get("metrics", []) if not metric.get("passed", False)
        ]
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


def render_html(summary: dict[str, Any]) -> str:
    """Render the static HTML eval report."""

    rows = "\n".join(
        "<tr>"
        f"<td>{escape(gate['name'])}</td>"
        f"<td>{escape(gate['status'].upper())}</td>"
        f"<td>{gate['score']}/{gate['total']}</td>"
        f"<td><code>{escape(gate['rerun'])}</code></td>"
        "</tr>"
        for gate in summary["gates"]
    )
    return f"""<!doctype html>
<html>
<head><meta charset="utf-8"><title>Thesys Eval Report</title></head>
<body>
<h1>Thesys Eval Report</h1>
<p>Generated: {escape(summary['generated_at'])}</p>
<p>Result: {escape(summary['status'])} ({summary['score']}/{summary['total']})</p>
<table border="1" cellspacing="0" cellpadding="6">
<tr><th>Gate</th><th>Status</th><th>Score</th><th>Rerun</th></tr>
{rows}
</table>
<p>Changelog: docs/AI_CHANGELOG.md</p>
</body>
</html>
"""


def display_path(path: Path, *, repo_root: Path = REPO_ROOT) -> str:
    """Render paths relative to the repo when possible."""

    return str(path.relative_to(repo_root)) if path.is_relative_to(repo_root) else str(path)


def escape(value: Any) -> str:
    """Escape text for the static HTML report."""

    return (
        str(value)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )
