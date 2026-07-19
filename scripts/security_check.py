#!/usr/bin/env python3
"""Run the local security, governance, egress, redaction, and audit checks."""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
API_DIR = ROOT / "apps" / "api"


def main() -> int:
    parser = argparse.ArgumentParser(description="Run Thesys security checks.")
    parser.add_argument("--strict-audit", action="store_true", help="Fail on audit tool failures.")
    args = parser.parse_args()

    python = API_DIR / ".venv" / "bin" / "python"
    api_python = str(python if python.exists() else Path(sys.executable))
    checks = [
        _run(
            [
                api_python,
                "-m",
                "pytest",
                "app/tests/test_security_governance.py",
                "app/tests/test_tool_boundary.py",
                "app/tests/test_mcp_adapter.py",
                "app/tests/test_langsmith_observability.py",
                "-q",
            ],
            cwd=API_DIR,
        ),
        _run([sys.executable, "scripts/eval_ai_quality.py", "--json"], cwd=ROOT),
        _run(
            [
                sys.executable,
                "scripts/audit_dependencies.py",
                *(["--strict"] if args.strict_audit else []),
            ],
            cwd=ROOT,
        ),
    ]
    return 1 if any(code != 0 for code in checks) else 0


def _run(command: list[str], *, cwd: Path) -> int:
    print(f"$ {' '.join(command)}")
    return subprocess.run(command, cwd=cwd, check=False).returncode


if __name__ == "__main__":
    raise SystemExit(main())
