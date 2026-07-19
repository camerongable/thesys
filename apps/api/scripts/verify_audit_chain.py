#!/usr/bin/env python3
"""Verify the tamper-evident audit chain for every workspace or one workspace."""

import argparse
import sys
import uuid
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.config import get_settings  # noqa: E402
from app.services.audit_chain_service import verify_audit_chains  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database-url")
    parser.add_argument("--workspace-id", type=uuid.UUID)
    args = parser.parse_args()

    settings = get_settings()
    database_url = args.database_url or settings.migration_database_url or settings.database_url
    engine = create_engine(database_url, pool_pre_ping=True)
    with Session(engine) as db:
        results = verify_audit_chains(db, workspace_id=args.workspace_id)

    if not results:
        print("No audit events found.")
        return 0
    invalid_results = [result for result in results if not result.valid]
    for result in results:
        outcome = "valid" if result.valid else f"invalid: {result.error}"
        print(f"{result.workspace_id}: {result.event_count} events, {outcome}")
    return 1 if invalid_results else 0


if __name__ == "__main__":
    raise SystemExit(main())
