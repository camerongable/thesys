from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[5]


def test_pre_authentication_event_retention_migration_limits_definer_function_to_worker() -> None:
    migration = (
        REPO_ROOT
        / "apps/api/alembic/versions/0036_pre_authentication_event_retention.py"
    ).read_text()

    assert "SECURITY DEFINER" in migration
    assert "SET search_path = pg_catalog, public" in migration
    assert "workspace_id IS NULL" in migration
    assert "user_id IS NULL" in migration
    assert "OWNER TO thesys_migration" in migration
    assert "REVOKE ALL ON FUNCTION" in migration
    assert "GRANT EXECUTE ON FUNCTION" in migration
    assert '"thesys_worker"' in migration
    assert '"thesys_api"' not in migration
