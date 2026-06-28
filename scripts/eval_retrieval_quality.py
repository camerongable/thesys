#!/usr/bin/env python3
"""Run credential-free golden retrieval, reranking, and citation checks."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
API_DIR = ROOT / "apps" / "api"
API_PYTHON = API_DIR / ".venv" / "bin" / "python"
if API_PYTHON.exists() and Path(sys.executable).resolve() != API_PYTHON.resolve():
    os.execv(str(API_PYTHON), [str(API_PYTHON), *sys.argv])

sys.path.insert(0, str(API_DIR))

from app.core.config import get_settings  # noqa: E402
from app.services.retrieval_quality_eval_service import run_golden_retrieval_eval  # noqa: E402


def main() -> int:
    report = run_golden_retrieval_eval(get_settings())
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
