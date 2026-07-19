"""allow quarantined evidence sources

Revision ID: 0033_evidence_quarantine
Revises: 0032_session_revocations
Create Date: 2026-07-18 00:00:00.000000
"""

from alembic import op

revision = "0033_evidence_quarantine"
down_revision = "0032_session_revocations"
branch_labels = None
depends_on = None

TABLE_NAME = "evidence_sources"
CONSTRAINT_NAME = "ck_evidence_sources_ingestion_status"
READY_STATUSES = "'pending','processing','ready','failed','quarantined'"
PREVIOUS_STATUSES = "'pending','processing','ready','failed'"


def upgrade() -> None:
    op.drop_constraint(CONSTRAINT_NAME, TABLE_NAME, type_="check")
    op.create_check_constraint(
        CONSTRAINT_NAME,
        TABLE_NAME,
        f"ingestion_status in ({READY_STATUSES})",
    )


def downgrade() -> None:
    op.execute(
        "DO $quarantine_guard$ "
        "BEGIN "
        f"IF EXISTS (SELECT 1 FROM {TABLE_NAME} WHERE ingestion_status = 'quarantined') THEN "
        "RAISE EXCEPTION 'Cannot downgrade while quarantined evidence sources exist'; "
        "END IF; "
        "END $quarantine_guard$"
    )
    op.drop_constraint(CONSTRAINT_NAME, TABLE_NAME, type_="check")
    op.create_check_constraint(
        CONSTRAINT_NAME,
        TABLE_NAME,
        f"ingestion_status in ({PREVIOUS_STATUSES})",
    )
