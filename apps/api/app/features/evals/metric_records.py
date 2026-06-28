"""Pure metric-record builders shared by local eval scripts."""

from typing import Any

from app.schemas.evals import EvalGateMetricRecord


def metric(
    key: str,
    label: str,
    passed: bool,
    observed: Any,
    expected: str,
    *,
    warnings: list[str] | None = None,
) -> dict[str, Any]:
    """Build the stable metric shape used by eval reports and gates."""

    record = {
        "key": key,
        "label": label,
        "passed": passed,
        "observed": observed,
        "expected": expected,
    }
    if warnings is not None:
        record["warnings"] = warnings
    shaped = EvalGateMetricRecord.model_validate(record).model_dump()
    if warnings is None:
        shaped.pop("warnings", None)
    return shaped
