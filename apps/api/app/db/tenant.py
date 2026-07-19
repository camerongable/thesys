import uuid
from dataclasses import dataclass
from typing import Protocol

from sqlalchemy import event, text
from sqlalchemy.engine import Connection
from sqlalchemy.orm import Session

TENANT_CONTEXT_SESSION_KEY = "thesys_tenant_context"


class TenantPrincipal(Protocol):
    user_id: uuid.UUID
    workspace_id: uuid.UUID


@dataclass(frozen=True)
class TenantContext:
    workspace_id: uuid.UUID
    user_id: uuid.UUID


def bind_tenant_context(session: Session, principal: TenantPrincipal) -> TenantContext:
    context = TenantContext(
        workspace_id=uuid.UUID(str(principal.workspace_id)),
        user_id=uuid.UUID(str(principal.user_id)),
    )
    transaction_is_active = session.in_transaction()
    session.info[TENANT_CONTEXT_SESSION_KEY] = context
    connection = session.connection()
    if transaction_is_active:
        apply_tenant_context_to_connection(connection, context)
    return context


def get_bound_tenant_context(session: Session) -> TenantContext | None:
    context = session.info.get(TENANT_CONTEXT_SESSION_KEY)
    return context if isinstance(context, TenantContext) else None


def apply_tenant_context_to_connection(
    connection: Connection,
    context: TenantContext,
) -> None:
    if connection.dialect.name != "postgresql":
        return
    connection.execute(
        text(
            "SELECT "
            "set_config('app.workspace_id', :workspace_id, true), "
            "set_config('app.user_id', :user_id, true)"
        ),
        {
            "workspace_id": str(context.workspace_id),
            "user_id": str(context.user_id),
        },
    )


@event.listens_for(Session, "after_begin")
def _reapply_tenant_context(
    session: Session,
    _transaction: object,
    connection: Connection,
) -> None:
    context = get_bound_tenant_context(session)
    if context is not None:
        apply_tenant_context_to_connection(connection, context)
