#!/usr/bin/env python3
"""Static import-boundary check for Sprint 59 feature packages."""

from __future__ import annotations

import ast
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
FEATURES_ROOT = REPO_ROOT / "apps/api/app/features"

FORBIDDEN_PREFIXES = (
    "app.services",
    "app.routers",
)

ALLOWED_PREFIXES = (
    "app.ai",
    "app.common",
    "app.core",
    "app.db",
    "app.features",
    "app.mcp",
    "app.schemas",
)


def _imports(path: Path) -> list[tuple[int, str]]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    found: list[tuple[int, str]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                found.append((node.lineno, alias.name))
        elif isinstance(node, ast.ImportFrom) and node.module:
            found.append((node.lineno, node.module))
    return found


def _relative(path: Path) -> str:
    return str(path.relative_to(REPO_ROOT))


def main() -> int:
    violations: list[str] = []
    if not FEATURES_ROOT.exists():
        print("No feature packages found.")
        return 0

    for path in sorted(FEATURES_ROOT.rglob("*.py")):
        for lineno, module in _imports(path):
            if module.startswith(FORBIDDEN_PREFIXES):
                violations.append(f"{_relative(path)}:{lineno} imports {module}")

    if violations:
        print("Feature boundary violations:")
        for violation in violations:
            print(f"- {violation}")
        print(
            "\nFeature packages may depend on common packages and explicit "
            "feature APIs, but not compatibility services or routers."
        )
        return 1

    print(
        "Feature boundary check passed. Allowed app-level prefixes: "
        + ", ".join(ALLOWED_PREFIXES)
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
