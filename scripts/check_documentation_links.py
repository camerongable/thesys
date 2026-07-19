#!/usr/bin/env python3
"""Verify local Markdown link targets in the maintained documentation set."""

from __future__ import annotations

import re
import sys
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
DOCUMENTS = [REPOSITORY_ROOT / "README.md", *sorted((REPOSITORY_ROOT / "docs").rglob("*.md"))]
LINK_PATTERN = re.compile(r"(?<!!)\[[^\]]*\]\(([^)]+)\)")
CODE_PATH_PATTERN = re.compile(
    r"`((?:apps|docs|scripts|security|infra|policies|\.github)/[^`\s,;:()]+\.(?:py|ts|tsx|md|yaml|yml|toml|json|rego))`"
)
EXTERNAL_PREFIXES = ("http://", "https://", "mailto:", "#")


def local_target(raw_target: str) -> str | None:
    target = raw_target.strip().strip("<>")
    if not target or target.startswith(EXTERNAL_PREFIXES):
        return None
    return target.split("#", maxsplit=1)[0]


def main() -> int:
    missing: list[str] = []
    for document in DOCUMENTS:
        text = document.read_text(encoding="utf-8")
        for raw_target in LINK_PATTERN.findall(text):
            target = local_target(raw_target)
            if target is None:
                continue
            resolved = (document.parent / target).resolve()
            if not resolved.exists() or REPOSITORY_ROOT not in resolved.parents and resolved != REPOSITORY_ROOT:
                missing.append(f"{document.relative_to(REPOSITORY_ROOT)} -> {raw_target}")
        for code_path in CODE_PATH_PATTERN.findall(text):
            if "*" in code_path:
                continue
            if not (REPOSITORY_ROOT / code_path).exists():
                missing.append(f"{document.relative_to(REPOSITORY_ROOT)} -> `{code_path}`")
    if missing:
        print("Broken local Markdown links:", file=sys.stderr)
        print("\n".join(f"- {item}" for item in missing), file=sys.stderr)
        return 1
    print(f"Validated {len(DOCUMENTS)} Markdown documents with no broken local links or code paths.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
