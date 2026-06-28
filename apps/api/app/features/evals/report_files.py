"""File-backed eval report readers used by API routes and Inspect surfaces."""

import json
import os
from pathlib import Path
from typing import Any

from app.features.evals import report_failures

REPO_ROOT = Path(__file__).resolve().parents[5]
REPORT_DIR_ENV = "THESYS_EVAL_REPORT_DIR"
DEFAULT_REPORT_DIR = REPO_ROOT / "reports" / "evals"


def read_latest_report() -> dict[str, Any]:
    """Return the most recent local eval report if the quality gate has run."""

    path = report_dir() / "latest.json"
    if not path.exists():
        return report_failures.missing_report()
    return read_json(path)


def read_eval_trends(limit: int = 20) -> list[dict[str, Any]]:
    """Read recent file-backed eval trend records."""

    path = report_dir() / "eval_runs.jsonl"
    if not path.exists():
        return []
    records = []
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        return [report_failures.unreadable_trend_file(path, exc)]
    for line in lines:
        if not line.strip():
            continue
        try:
            records.append(json.loads(line))
        except json.JSONDecodeError:
            records.append(report_failures.malformed_trend_record())
    return records[-max(1, min(limit, 100)) :]


def report_dir() -> Path:
    """Resolve the local eval report directory from env or repo defaults."""

    configured = os.environ.get(REPORT_DIR_ENV)
    return Path(configured).expanduser() if configured else DEFAULT_REPORT_DIR


def read_json(path: Path) -> dict[str, Any]:
    """Read JSON report files with a UI-safe malformed-file warning."""

    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return report_failures.malformed_report(path)
    except OSError as exc:
        return report_failures.unreadable_report(path, exc)
