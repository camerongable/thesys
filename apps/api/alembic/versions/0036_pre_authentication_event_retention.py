"""add worker-only purge for expired pre-authentication events

Revision ID: 0036_pre_auth_event_retention
Revises: 0035_pii_token_mapping_retention
Create Date: 2026-07-18 00:00:00.000000
"""

from alembic import op

revision = "0036_pre_auth_event_retention"
down_revision = "0035_pii_token_mapping_retention"
branch_labels = None
depends_on = None

FUNCTION_NAME = "purge_expired_pre_authentication_events"


def upgrade() -> None:
    op.execute(
        f"""
        CREATE FUNCTION public.{FUNCTION_NAME}(p_cutoff timestamptz)
        RETURNS integer
        LANGUAGE sql
        SECURITY DEFINER
        SET search_path = pg_catalog, public
        AS $$
            WITH deleted AS (
                DELETE FROM public.authentication_events
                WHERE workspace_id IS NULL
                  AND user_id IS NULL
                  AND created_at <= p_cutoff
                RETURNING 1
            )
            SELECT count(*)::integer FROM deleted;
        $$;
        """
    )
    op.execute(f"ALTER FUNCTION public.{FUNCTION_NAME}(timestamptz) OWNER TO thesys_migration")
    op.execute(f"REVOKE ALL ON FUNCTION public.{FUNCTION_NAME}(timestamptz) FROM PUBLIC")
    _grant_execute_if_role_exists("thesys_worker")


def downgrade() -> None:
    _revoke_execute_if_role_exists("thesys_worker")
    op.execute(f"DROP FUNCTION public.{FUNCTION_NAME}(timestamptz)")


def _grant_execute_if_role_exists(role: str) -> None:
    _execute_if_role_exists(
        role,
        f"GRANT EXECUTE ON FUNCTION public.{FUNCTION_NAME}(timestamptz) TO {role}",
    )


def _revoke_execute_if_role_exists(role: str) -> None:
    _execute_if_role_exists(
        role,
        f"REVOKE ALL ON FUNCTION public.{FUNCTION_NAME}(timestamptz) FROM {role}",
    )


def _execute_if_role_exists(role: str, statement: str) -> None:
    escaped_statement = statement.replace("'", "''")
    op.execute(
        "DO $role_grant$ "
        "BEGIN "
        f"IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = '{role}') THEN "
        f"EXECUTE '{escaped_statement}'; "
        "END IF; "
        "END $role_grant$"
    )
