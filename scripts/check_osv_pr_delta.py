#!/usr/bin/env python3
"""Fail CI only when a pull request adds an OSV dependency finding."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def parse_findings(path: Path) -> set[tuple[str, str, str, str]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    findings: set[tuple[str, str, str, str]] = set()
    for result in payload.get("results", []):
        for package_group in result.get("packages", []):
            package = package_group.get("package", {})
            ecosystem = str(package.get("ecosystem", ""))
            name = str(package.get("name", ""))
            version = str(package.get("version", ""))
            for group in package_group.get("groups", []):
                for vulnerability_id in group.get("ids", []):
                    findings.add((ecosystem, name, version, str(vulnerability_id)))
    return findings


def main() -> int:
    parser = argparse.ArgumentParser(description="Compare base and pull-request OSV findings.")
    parser.add_argument("--baseline", type=Path, required=True)
    parser.add_argument("--current", type=Path, required=True)
    args = parser.parse_args()

    introduced = sorted(parse_findings(args.current) - parse_findings(args.baseline))
    if not introduced:
        print("No new OSV dependency findings were introduced by this pull request.")
        return 0

    print("New OSV dependency findings:")
    for ecosystem, name, version, vulnerability_id in introduced:
        print(f"- {ecosystem}:{name}@{version}: {vulnerability_id}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
