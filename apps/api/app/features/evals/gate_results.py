"""Pure quality-gate result DTO builders."""

import json
from typing import Any

from app.schemas.evals import EvalGateResultRead


def parse_json_output(stdout: str) -> dict[str, Any]:
    """Parse JSON gate stdout, tolerating log lines around the JSON payload."""

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


def json_command_gate(
    name: str,
    command: list[str],
    *,
    purpose: str,
    returncode: int,
    stdout: str,
    stderr: str,
) -> dict[str, Any]:
    """Build a gate result from a subprocess that emits JSON metrics."""

    parsed = parse_json_output(stdout)
    status = "pass" if returncode == 0 and bool(parsed.get("passed")) else "fail"
    return _gate_result(
        name=name,
        purpose=purpose,
        status=status,
        passed=status == "pass",
        score=int(parsed.get("score") or (1 if status == "pass" else 0)),
        total=int(parsed.get("total") or 1),
        metrics=parsed.get("metrics") or [],
        command=command,
        returncode=returncode,
        stdout_tail=stdout[-2500:],
        stderr_tail=stderr[-2500:],
        rerun=" ".join(command),
    )


def command_gate(
    name: str,
    command: list[str],
    *,
    purpose: str,
    returncode: int,
    stdout: str,
    stderr: str,
) -> dict[str, Any]:
    """Build a gate result from a plain command exit code."""

    status = "pass" if returncode == 0 else "fail"
    return _gate_result(
        name=name,
        purpose=purpose,
        status=status,
        passed=status == "pass",
        score=1 if status == "pass" else 0,
        total=1,
        metrics=[
            {
                "key": name,
                "label": name.replace("_", " ").title(),
                "passed": status == "pass",
                "observed": f"exit {returncode}",
                "expected": "exit 0",
            }
        ],
        command=command,
        returncode=returncode,
        stdout_tail=stdout[-2500:],
        stderr_tail=stderr[-2500:],
        rerun=" ".join(command),
    )


def warning_gate(name: str, message: str, rerun: str) -> dict[str, Any]:
    """Build the stable report shape for unavailable or intentionally skipped gates."""
    return _gate_result(
        name=name,
        purpose=message,
        status="warn",
        passed=True,
        score=0,
        total=0,
        metrics=[
            {
                "key": f"{name}_unavailable",
                "label": name.replace("_", " ").title(),
                "passed": True,
                "observed": "unavailable",
                "expected": message,
            }
        ],
        command=[],
        returncode=None,
        stdout_tail="",
        stderr_tail="",
        rerun=rerun,
    )


def _gate_result(**payload: Any) -> dict[str, Any]:
    """Validate and serialize the public quality-gate result shape."""

    return EvalGateResultRead.model_validate(payload).model_dump()
