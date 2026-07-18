import uuid
from types import SimpleNamespace

import pytest
from pydantic import ValidationError
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.db import tenant
from app.db.tenant import (
    TenantContext,
    apply_tenant_context_to_connection,
    bind_tenant_context,
    get_bound_tenant_context,
)


def test_tenant_context_is_reapplied_after_each_session_transaction(
    monkeypatch,
) -> None:
    applied: list[TenantContext] = []
    monkeypatch.setattr(
        tenant,
        "apply_tenant_context_to_connection",
        lambda _connection, context: applied.append(context),
    )
    engine = create_engine("sqlite+pysqlite:///:memory:")
    principal = SimpleNamespace(user_id=uuid.uuid4(), workspace_id=uuid.uuid4())

    with Session(engine) as session:
        context = bind_tenant_context(session, principal)
        assert applied == [context]

        session.commit()
        session.execute(select(1))

        assert applied == [context, context]
        assert get_bound_tenant_context(session) == context


def test_binding_into_an_active_transaction_applies_context_immediately(
    monkeypatch,
) -> None:
    applied: list[TenantContext] = []
    monkeypatch.setattr(
        tenant,
        "apply_tenant_context_to_connection",
        lambda _connection, context: applied.append(context),
    )
    engine = create_engine("sqlite+pysqlite:///:memory:")
    principal = SimpleNamespace(user_id=uuid.uuid4(), workspace_id=uuid.uuid4())

    with Session(engine) as session:
        session.execute(select(1))
        context = bind_tenant_context(session, principal)

        assert applied == [context]


def test_postgres_context_uses_transaction_local_settings() -> None:
    executions: list[tuple[str, dict[str, str]]] = []

    class FakeConnection:
        dialect = SimpleNamespace(name="postgresql")

        def execute(self, statement, parameters) -> None:
            executions.append((str(statement), parameters))

    context = TenantContext(workspace_id=uuid.uuid4(), user_id=uuid.uuid4())

    apply_tenant_context_to_connection(FakeConnection(), context)  # type: ignore[arg-type]

    assert len(executions) == 1
    statement, parameters = executions[0]
    assert "set_config('app.workspace_id', :workspace_id, true)" in statement
    assert "set_config('app.user_id', :user_id, true)" in statement
    assert parameters == {
        "workspace_id": str(context.workspace_id),
        "user_id": str(context.user_id),
    }


def test_hosted_configuration_rejects_bootstrap_or_wrong_runtime_role() -> None:
    with pytest.raises(ValidationError, match="scoped runtime role"):
        Settings(
            environment="production",
            auth_mode="api_key",
            secret_provider="cloud",
            database_runtime_role="api",
            database_url="postgresql+psycopg://postgres:secret@db.example/thesys",
            malware_scanner_mode="clamav",
        )

    settings = Settings(
        environment="production",
        auth_mode="api_key",
        secret_provider="cloud",
        database_runtime_role="worker",
        database_url="postgresql+psycopg://thesys_worker:secret@db.example/thesys",
        object_storage_mode="s3",
        s3_endpoint_url="https://s3.example.com",
        s3_verify_bucket_security=True,
        malware_scanner_mode="clamav",
    )
    assert settings.database_runtime_role == "worker"
