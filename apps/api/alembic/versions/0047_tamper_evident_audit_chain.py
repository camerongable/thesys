"""add tamper-evident audit event chain

Revision ID: 0047_tamper_evident_audit_chain
Revises: 0046_research_sprint_workflow_usage
Create Date: 2026-07-18 00:00:00.000000
"""

import hashlib
import json
from datetime import UTC, datetime

import sqlalchemy as sa

from alembic import context, op

revision = "0047_tamper_evident_audit_chain"
down_revision = "0046_research_sprint_workflow_usage"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("audit_events", sa.Column("actor_identity", sa.String(length=160), nullable=True))
    op.add_column("audit_events", sa.Column("policy_decision", sa.String(length=40), nullable=True))
    op.add_column(
        "audit_events",
        sa.Column("resource_identifier", sa.String(length=200), nullable=True),
    )
    op.add_column(
        "audit_events",
        sa.Column("previous_event_hash", sa.String(length=64), nullable=True),
    )
    op.add_column("audit_events", sa.Column("event_hash", sa.String(length=64), nullable=True))

    if not context.is_offline_mode():
        _backfill_audit_chain()

    op.alter_column("audit_events", "actor_identity", nullable=False)
    op.alter_column("audit_events", "policy_decision", nullable=False)
    op.alter_column("audit_events", "resource_identifier", nullable=False)
    op.alter_column("audit_events", "event_hash", nullable=False)
    op.create_index("ix_audit_events_event_hash", "audit_events", ["event_hash"])
    op.execute(
        "CREATE OR REPLACE FUNCTION prevent_audit_event_timestamp_change() "
        "RETURNS trigger AS $$ "
        "BEGIN "
        "IF NEW.created_at IS DISTINCT FROM OLD.created_at THEN "
        "RAISE EXCEPTION 'audit event timestamps are immutable'; "
        "END IF; "
        "RETURN NEW; "
        "END; "
        "$$ LANGUAGE plpgsql"
    )
    op.execute(
        "CREATE TRIGGER audit_events_timestamp_immutable "
        "BEFORE UPDATE ON audit_events "
        "FOR EACH ROW EXECUTE FUNCTION prevent_audit_event_timestamp_change()"
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS audit_events_timestamp_immutable ON audit_events")
    op.execute("DROP FUNCTION IF EXISTS prevent_audit_event_timestamp_change()")
    op.drop_index("ix_audit_events_event_hash", table_name="audit_events")
    op.drop_column("audit_events", "event_hash")
    op.drop_column("audit_events", "previous_event_hash")
    op.drop_column("audit_events", "resource_identifier")
    op.drop_column("audit_events", "policy_decision")
    op.drop_column("audit_events", "actor_identity")


def _backfill_audit_chain() -> None:
    connection = op.get_bind()
    rows = connection.execute(
        sa.text(
            "SELECT id, workspace_id, project_id, user_id, event_type, actor_type, "
            "entity_type, entity_id, summary, risk_level, metadata, created_at "
            "FROM audit_events ORDER BY workspace_id, created_at, id"
        )
    ).mappings()
    previous_by_workspace: dict[str, str | None] = {}
    for row in rows:
        workspace_id = str(row["workspace_id"])
        actor_identity = _actor_identity(row["actor_type"], row["user_id"])
        policy_decision = _policy_decision(row["event_type"])
        resource_identifier = _resource_identifier(
            workspace_id,
            row["project_id"],
            row["entity_type"],
            row["entity_id"],
        )
        previous_event_hash = previous_by_workspace.get(workspace_id)
        event_hash = _calculate_event_hash(
            row,
            actor_identity,
            policy_decision,
            resource_identifier,
            previous_event_hash,
        )
        connection.execute(
            sa.text(
                "UPDATE audit_events SET actor_identity = :actor_identity, "
                "policy_decision = :policy_decision, resource_identifier = :resource_identifier, "
                "previous_event_hash = :previous_event_hash, event_hash = :event_hash "
                "WHERE id = :id"
            ),
            {
                "id": row["id"],
                "actor_identity": actor_identity,
                "policy_decision": policy_decision,
                "resource_identifier": resource_identifier,
                "previous_event_hash": previous_event_hash,
                "event_hash": event_hash,
            },
        )
        previous_by_workspace[workspace_id] = event_hash


def _calculate_event_hash(
    row: sa.RowMapping,
    actor_identity: str,
    policy_decision: str,
    resource_identifier: str,
    previous_event_hash: str | None,
) -> str:
    payload = {
        "actor_identity": actor_identity,
        "actor_type": row["actor_type"],
        "created_at": _timestamp_value(row["created_at"]),
        "entity_id": str(row["entity_id"]) if row["entity_id"] is not None else None,
        "entity_type": row["entity_type"],
        "event_id": str(row["id"]),
        "event_metadata": row["metadata"] or {},
        "event_type": row["event_type"],
        "policy_decision": policy_decision,
        "previous_event_hash": previous_event_hash,
        "project_id": str(row["project_id"]) if row["project_id"] is not None else None,
        "resource_identifier": resource_identifier,
        "risk_level": row["risk_level"],
        "summary": row["summary"],
        "user_id": str(row["user_id"]) if row["user_id"] is not None else None,
        "workspace_id": str(row["workspace_id"]),
    }
    encoded = json.dumps(
        payload,
        default=str,
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _actor_identity(actor_type: str, user_id: object | None) -> str:
    if actor_type == "user" and user_id is not None:
        return f"user:{user_id}"
    return f"{actor_type}:service"


def _policy_decision(event_type: str) -> str:
    normalized = event_type.casefold()
    if any(token in normalized for token in ("denied", "rejected", "blocked")):
        return "denied"
    if "approved" in normalized:
        return "approved"
    return "recorded"


def _resource_identifier(
    workspace_id: str,
    project_id: object | None,
    entity_type: str | None,
    entity_id: object | None,
) -> str:
    if entity_type is not None and entity_id is not None:
        return f"{entity_type}:{entity_id}"
    if project_id is not None:
        return f"project:{project_id}"
    return f"workspace:{workspace_id}"


def _timestamp_value(value: datetime) -> str:
    normalized = value if value.tzinfo is not None else value.replace(tzinfo=UTC)
    return normalized.astimezone(UTC).isoformat().replace("+00:00", "Z")
