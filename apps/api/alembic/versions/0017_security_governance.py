"""add security governance and approval records

Revision ID: 0017_security_governance
Revises: 0016_mcp_tool_boundary
Create Date: 2026-06-11 00:00:00.000000
"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "0017_security_governance"
down_revision = "0016_mcp_tool_boundary"
branch_labels = None
depends_on = None


def _json_type() -> sa.JSON:
    return sa.JSON().with_variant(postgresql.JSONB(), "postgresql")


def upgrade() -> None:
    op.execute("UPDATE workspace_members SET role = 'editor' WHERE role = 'member'")
    op.drop_constraint("ck_workspace_members_role", "workspace_members", type_="check")
    op.create_check_constraint(
        "ck_workspace_members_role",
        "workspace_members",
        "role in ('owner','admin','editor','viewer')",
    )

    op.create_table(
        "audit_events",
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=True),
        sa.Column("user_id", sa.Uuid(), nullable=True),
        sa.Column("event_type", sa.String(length=120), nullable=False),
        sa.Column("actor_type", sa.String(length=20), nullable=False),
        sa.Column("entity_type", sa.String(length=80), nullable=True),
        sa.Column("entity_id", sa.Uuid(), nullable=True),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("risk_level", sa.String(length=20), nullable=True),
        sa.Column("metadata", _json_type(), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "actor_type in ('user','agent','system')",
            name="ck_audit_events_actor_type",
        ),
        sa.CheckConstraint(
            "risk_level in ('low','medium','high')",
            name="ck_audit_events_risk_level",
        ),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_audit_events_entity_id", "audit_events", ["entity_id"])
    op.create_index("ix_audit_events_entity_type", "audit_events", ["entity_type"])
    op.create_index("ix_audit_events_event_type", "audit_events", ["event_type"])
    op.create_index("ix_audit_events_project_id", "audit_events", ["project_id"])
    op.create_index("ix_audit_events_risk_level", "audit_events", ["risk_level"])
    op.create_index("ix_audit_events_user_id", "audit_events", ["user_id"])
    op.create_index("ix_audit_events_workspace_id", "audit_events", ["workspace_id"])

    op.create_table(
        "approval_requests",
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("request_type", sa.String(length=40), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("requested_by", sa.String(length=20), nullable=False),
        sa.Column("approved_by_user_id", sa.Uuid(), nullable=True),
        sa.Column("risk_level", sa.String(length=20), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("proposed_change", _json_type(), nullable=False),
        sa.Column("entity_type", sa.String(length=80), nullable=True),
        sa.Column("entity_id", sa.Uuid(), nullable=True),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "request_type in ("
            "'research_plan','memory_update','tool_invocation','validation_plan','decision'"
            ")",
            name="ck_approval_requests_request_type",
        ),
        sa.CheckConstraint(
            "requested_by in ('agent','user','system')",
            name="ck_approval_requests_requested_by",
        ),
        sa.CheckConstraint(
            "risk_level in ('low','medium','high')",
            name="ck_approval_requests_risk_level",
        ),
        sa.CheckConstraint(
            "status in ('pending','approved','rejected','expired')",
            name="ck_approval_requests_status",
        ),
        sa.ForeignKeyConstraint(["approved_by_user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_approval_requests_approved_by_user_id", "approval_requests", ["approved_by_user_id"])
    op.create_index("ix_approval_requests_entity_id", "approval_requests", ["entity_id"])
    op.create_index("ix_approval_requests_entity_type", "approval_requests", ["entity_type"])
    op.create_index("ix_approval_requests_project_id", "approval_requests", ["project_id"])
    op.create_index("ix_approval_requests_request_type", "approval_requests", ["request_type"])
    op.create_index("ix_approval_requests_risk_level", "approval_requests", ["risk_level"])
    op.create_index("ix_approval_requests_status", "approval_requests", ["status"])
    op.create_index("ix_approval_requests_workspace_id", "approval_requests", ["workspace_id"])


def downgrade() -> None:
    op.drop_index("ix_approval_requests_workspace_id", table_name="approval_requests")
    op.drop_index("ix_approval_requests_status", table_name="approval_requests")
    op.drop_index("ix_approval_requests_risk_level", table_name="approval_requests")
    op.drop_index("ix_approval_requests_request_type", table_name="approval_requests")
    op.drop_index("ix_approval_requests_project_id", table_name="approval_requests")
    op.drop_index("ix_approval_requests_entity_type", table_name="approval_requests")
    op.drop_index("ix_approval_requests_entity_id", table_name="approval_requests")
    op.drop_index("ix_approval_requests_approved_by_user_id", table_name="approval_requests")
    op.drop_table("approval_requests")

    op.drop_index("ix_audit_events_workspace_id", table_name="audit_events")
    op.drop_index("ix_audit_events_user_id", table_name="audit_events")
    op.drop_index("ix_audit_events_risk_level", table_name="audit_events")
    op.drop_index("ix_audit_events_project_id", table_name="audit_events")
    op.drop_index("ix_audit_events_event_type", table_name="audit_events")
    op.drop_index("ix_audit_events_entity_type", table_name="audit_events")
    op.drop_index("ix_audit_events_entity_id", table_name="audit_events")
    op.drop_table("audit_events")

    op.drop_constraint("ck_workspace_members_role", "workspace_members", type_="check")
    op.execute("UPDATE workspace_members SET role = 'member' WHERE role = 'editor'")
    op.create_check_constraint(
        "ck_workspace_members_role",
        "workspace_members",
        "role in ('owner','admin','member','viewer')",
    )
