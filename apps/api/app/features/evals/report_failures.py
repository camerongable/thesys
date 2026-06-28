"""UI-safe eval report and trend failure payload builders."""

from pathlib import Path
from typing import Any

from app.schemas.evals import EvalReportFailureRead


def missing_report() -> dict[str, Any]:
    """Report that no local quality-gate artifact exists yet."""

    return _failure(
        available=False,
        status="unavailable",
        message="No local eval report found. Run `python3 scripts/eval_quality_gate.py`.",
    )


def malformed_report(path: Path) -> dict[str, Any]:
    """Report that an eval JSON artifact could not be parsed."""

    return _failure(
        available=False,
        status="warning",
        message=f"Eval report is not valid JSON: {path}",
    )


def unreadable_report(path: Path, error: OSError) -> dict[str, Any]:
    """Report that an eval JSON artifact exists but cannot be read."""

    return _failure(
        available=False,
        status="warning",
        message=f"Eval report could not be read: {path} ({error.__class__.__name__})",
    )


def malformed_trend_record() -> dict[str, Any]:
    """Report a skipped malformed JSONL trend row."""

    return _failure(status="warning", message="Skipped malformed trend record.")


def unreadable_trend_file(path: Path, error: OSError) -> dict[str, Any]:
    """Report that eval trend history exists but cannot be read."""

    return _failure(
        status="warning",
        message=f"Eval trend file could not be read: {path} ({error.__class__.__name__})",
    )


def unwritable_trend_file(path: Path, error: OSError) -> dict[str, Any]:
    """Report that report artifacts were written but trend history was not."""

    return _failure(
        status="warning",
        message=f"Eval trend file could not be written: {path} ({error.__class__.__name__})",
    )


def _failure(**payload: Any) -> dict[str, Any]:
    """Validate and serialize UI-safe report failure payloads."""

    return EvalReportFailureRead.model_validate(payload).model_dump(exclude_none=True)
