"""add thesis canvas and evolution timeline

Revision ID: 0019_thesis_canvas
Revises: 0018_temporal_research
Create Date: 2026-06-13 00:00:00.000000
"""

import sqlalchemy as sa

from alembic import op

revision = "0019_thesis_canvas"
down_revision = "0018_temporal_research"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "thesis_canvases",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("original_idea", sa.Text(), nullable=False),
        sa.Column("current_thesis", sa.Text(), nullable=False),
        sa.Column("target_user", sa.Text(), nullable=False),
        sa.Column("problem", sa.Text(), nullable=False),
        sa.Column("current_workaround", sa.Text(), nullable=False),
        sa.Column("proposed_solution", sa.Text(), nullable=False),
        sa.Column("wedge", sa.Text(), nullable=False),
        sa.Column("biggest_unknown", sa.Text(), nullable=False),
        sa.Column("proof_needed", sa.Text(), nullable=False),
        sa.Column("rejected_directions", sa.JSON(), nullable=False),
        sa.Column("open_questions", sa.JSON(), nullable=False),
        sa.Column("created_by", sa.Uuid(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"]),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("project_id"),
    )
    op.create_index("ix_thesis_canvases_project_id", "thesis_canvases", ["project_id"])
    op.create_index("ix_thesis_canvases_workspace_id", "thesis_canvases", ["workspace_id"])

    op.create_table(
        "thesis_evolution_events",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("event_type", sa.String(length=40), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("change_summary", sa.Text(), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("source_entity_type", sa.String(length=40), nullable=True),
        sa.Column("source_entity_id", sa.Uuid(), nullable=True),
        sa.Column("origin", sa.String(length=20), nullable=False),
        sa.Column("created_by", sa.Uuid(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "event_type in ("
            "'original_idea','structured_thesis','research_update','wedge_change',"
            "'validation_blocker','decision','manual_update'"
            ")",
            name="ck_thesis_evolution_events_event_type",
        ),
        sa.CheckConstraint(
            "origin in ('user','agent','system')",
            name="ck_thesis_evolution_events_origin",
        ),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"]),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_thesis_evolution_events_event_type",
        "thesis_evolution_events",
        ["event_type"],
    )
    op.create_index(
        "ix_thesis_evolution_events_project_id",
        "thesis_evolution_events",
        ["project_id"],
    )
    op.create_index(
        "ix_thesis_evolution_events_workspace_id",
        "thesis_evolution_events",
        ["workspace_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_thesis_evolution_events_workspace_id", table_name="thesis_evolution_events")
    op.drop_index("ix_thesis_evolution_events_project_id", table_name="thesis_evolution_events")
    op.drop_index("ix_thesis_evolution_events_event_type", table_name="thesis_evolution_events")
    op.drop_table("thesis_evolution_events")
    op.drop_index("ix_thesis_canvases_workspace_id", table_name="thesis_canvases")
    op.drop_index("ix_thesis_canvases_project_id", table_name="thesis_canvases")
    op.drop_table("thesis_canvases")
