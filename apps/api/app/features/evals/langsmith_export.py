"""Pure LangSmith eval export payload and result shaping."""

from pathlib import Path
from typing import Any

from app.core.redaction import redact_payload
from app.features.evals import report_writer
from app.schemas.evals import EvalExportResultRead


def redacted_export_payload(summary: dict[str, Any]) -> dict[str, Any]:
    """Return the eval summary payload that is safe to write or upload."""

    return redact_payload(summary, redact_emails=True, max_string_length=2000)


def export_filename(generated_at: str) -> str:
    """Build the stable local export filename for an eval run timestamp."""

    return f"langsmith_export_{generated_at.replace(':', '')}.json"


def export_path(report_dir: Path, summary: dict[str, Any]) -> Path:
    """Return the local export path for a quality-gate summary."""

    return report_dir / export_filename(str(summary["generated_at"]))


def export_result(
    path: Path,
    *,
    repo_root: Path = report_writer.REPO_ROOT,
    uploaded: bool = False,
    status: str = "exported",
    message: str | None = None,
) -> dict[str, Any]:
    """Build the stable status object embedded in the quality-gate summary."""

    result = EvalExportResultRead(
        path=report_writer.display_path(path, repo_root=repo_root),
        uploaded=uploaded,
        status=status,
        message=message,
    ).model_dump(exclude_none=True)
    return result


def run_inputs(summary: dict[str, Any]) -> dict[str, Any]:
    """Project quality-gate metadata into LangSmith run inputs."""

    return {"sprint": summary["sprint"], "git_commit": summary["git_commit"]}
