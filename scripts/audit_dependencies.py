#!/usr/bin/env python3
"""Run local dependency audit commands without requiring every tool to be installed."""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit Python and Node dependencies.")
    parser.add_argument("--strict", action="store_true", help="Fail when audit tools fail or miss.")
    args = parser.parse_args()

    checks = [
        _run_python_audit(strict=args.strict),
        _run_pnpm_audit(strict=args.strict),
        _run_docker_review(strict=args.strict),
    ]
    return 1 if any(code != 0 for code in checks) else 0


def _run_python_audit(*, strict: bool) -> int:
    python = ROOT / "apps" / "api" / ".venv" / "bin" / "python"
    executable = str(python if python.exists() else Path(sys.executable))
    if _module_exists(executable, "pip_audit"):
        return _run([executable, "-m", "pip_audit"], strict=strict)

    print("python: pip-audit is not installed; run `python -m pip install pip-audit`.")
    _run([executable, "-m", "pip", "list", "--format=columns"], strict=False)
    return 1 if strict else 0


def _run_pnpm_audit(*, strict: bool) -> int:
    if shutil.which("pnpm") is None:
        print("node: pnpm is not installed; skipping pnpm audit.")
        return 1 if strict else 0
    return _run(["pnpm", "audit", "--prod"], strict=strict, timeout=120)


def _run_docker_review(*, strict: bool) -> int:
    compose_file = ROOT / "docker-compose.yml"
    if not compose_file.exists():
        print("docker: docker-compose.yml not found; skipping image inventory.")
        return 0
    if shutil.which("docker") is None:
        print("docker: docker is not installed; skipping image inventory.")
        return 1 if strict else 0
    return _run(["docker", "compose", "config", "--images"], strict=strict)


def _module_exists(python: str, module_name: str) -> bool:
    result = subprocess.run(
        [python, "-c", f"import {module_name.replace('-', '_')}"],
        cwd=ROOT,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
    )
    return result.returncode == 0


def _run(command: list[str], *, strict: bool, timeout: int | None = None) -> int:
    print(f"$ {' '.join(command)}")
    try:
        result = subprocess.run(command, cwd=ROOT, timeout=timeout, check=False)
    except subprocess.TimeoutExpired:
        print("command timed out")
        return 1 if strict else 0
    if result.returncode and not strict:
        print(f"command exited {result.returncode}; continuing because strict mode is disabled.")
        return 0
    return result.returncode


if __name__ == "__main__":
    raise SystemExit(main())
