import os
import uuid
from dataclasses import dataclass

import pytest
from sqlalchemy import create_engine, delete, select, text, update
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session

from app.db.models import (
    ApprovalRequest,
    Decision,
    EvidenceChunk,
    EvidenceSource,
    Project,
    ProjectMemoryItem,
    ResearchPlan,
    ResearchSprint,
    ToolInvocation,
    User,
    Workspace,
    WorkspaceMember,
)
from app.db.tenant import bind_tenant_context
from app.security.contracts import RLS_DIRECT_TENANT_TABLES, RLS_INHERITED_TENANT_TABLES


@dataclass(frozen=True)
class FixtureIdentity:
    user_id: uuid.UUID
    workspace_id: uuid.UUID


@dataclass(frozen=True)
class TenantRecords:
    project_id: uuid.UUID
    source_id: uuid.UUID
    chunk_id: uuid.UUID
    memory_id: uuid.UUID
    approval_id: uuid.UUID
    tool_invocation_id: uuid.UUID
    decision_id: uuid.UUID
    sprint_id: uuid.UUID


def test_postgres_rls_blocks_direct_cross_tenant_reads_and_writes() -> None:
    database_url = os.getenv("RLS_TEST_DATABASE_URL")
    if not database_url:
        pytest.skip("RLS_TEST_DATABASE_URL is required for the live Postgres RLS test.")

    engine = create_engine(database_url, pool_pre_ping=True)
    identity_a: FixtureIdentity | None = None
    identity_b: FixtureIdentity | None = None
    records_a: TenantRecords | None = None
    records_b: TenantRecords | None = None
    try:
        with engine.connect() as connection:
            role = connection.execute(
                text(
                    "SELECT rolname, rolsuper, rolbypassrls "
                    "FROM pg_roles WHERE rolname = current_user"
                )
            ).mappings().one()
            assert dict(role) == {
                "rolname": "thesys_api",
                "rolsuper": False,
                "rolbypassrls": False,
            }
            expected_rls_tables = RLS_DIRECT_TENANT_TABLES | RLS_INHERITED_TENANT_TABLES
            forced_rls_tables = set(
                connection.scalars(
                    text(
                        "SELECT relname FROM pg_class "
                        "WHERE relnamespace = 'public'::regnamespace "
                        "AND relname = ANY(:table_names) "
                        "AND relrowsecurity AND relforcerowsecurity"
                    ),
                    {"table_names": list(expected_rls_tables)},
                )
            )
            assert forced_rls_tables == expected_rls_tables

        identity_a, identity_b = _create_identities(engine)
        records_a = _create_tenant_records(engine, identity_a, "A")
        records_b = _create_tenant_records(engine, identity_b, "B")

        with Session(engine) as session_a:
            bind_tenant_context(session_a, identity_a)

            assert session_a.get(Project, records_b.project_id) is None
            assert session_a.get(EvidenceChunk, records_b.chunk_id) is None
            assert session_a.get(ProjectMemoryItem, records_b.memory_id) is None
            assert session_a.get(Decision, records_b.decision_id) is None
            assert session_a.get(ResearchSprint, records_b.sprint_id) is None

            source_ids = set(session_a.scalars(select(EvidenceSource.id)))
            assert records_a.source_id in source_ids
            assert records_b.source_id not in source_ids

            vector_hits = list(
                session_a.scalars(
                    select(EvidenceChunk).order_by(
                        EvidenceChunk.embedding.cosine_distance([0.25] * 1536)
                    )
                )
            )
            assert {chunk.id for chunk in vector_hits} == {records_a.chunk_id}

            approval_result = session_a.execute(
                update(ApprovalRequest)
                .where(ApprovalRequest.id == records_b.approval_id)
                .values(status="approved", approved_by_user_id=identity_a.user_id)
            )
            tool_result = session_a.execute(
                update(ToolInvocation)
                .where(ToolInvocation.id == records_b.tool_invocation_id)
                .values(status="approved", approved_by_user_id=identity_a.user_id)
            )
            assert approval_result.rowcount == 0
            assert tool_result.rowcount == 0

            session_a.add(
                Project(
                    workspace_id=identity_b.workspace_id,
                    name="Cross-tenant insert",
                    created_by=identity_a.user_id,
                )
            )
            with pytest.raises(DBAPIError):
                session_a.commit()
            session_a.rollback()

            assert session_a.get(Project, records_a.project_id) is not None
            assert session_a.get(Project, records_b.project_id) is None
    finally:
        if records_a is not None and identity_a is not None:
            _delete_tenant_records(engine, identity_a, records_a)
        if records_b is not None and identity_b is not None:
            _delete_tenant_records(engine, identity_b, records_b)
        if identity_a is not None and identity_b is not None:
            _delete_identities(engine, identity_a, identity_b)
        engine.dispose()


def _create_identities(engine) -> tuple[FixtureIdentity, FixtureIdentity]:
    with Session(engine) as session:
        identities: list[FixtureIdentity] = []
        for label in ("A", "B"):
            unique = uuid.uuid4().hex
            user = User(
                external_auth_id=f"rls-test:{unique}",
                email=f"rls-{unique}@example.com",
                display_name=f"RLS User {label}",
            )
            session.add(user)
            session.flush()
            workspace = Workspace(name=f"RLS Workspace {label} {unique}", created_by=user.id)
            session.add(workspace)
            session.flush()
            session.add(
                WorkspaceMember(workspace_id=workspace.id, user_id=user.id, role="owner")
            )
            identities.append(FixtureIdentity(user_id=user.id, workspace_id=workspace.id))
        session.commit()
        return identities[0], identities[1]


def _create_tenant_records(
    engine,
    identity: FixtureIdentity,
    label: str,
) -> TenantRecords:
    with Session(engine) as session:
        bind_tenant_context(session, identity)
        project = Project(
            workspace_id=identity.workspace_id,
            name=f"RLS Project {label}",
            created_by=identity.user_id,
        )
        session.add(project)
        session.flush()
        source = EvidenceSource(
            workspace_id=identity.workspace_id,
            project_id=project.id,
            source_type="note",
            title=f"RLS Evidence {label}",
            raw_text=f"Tenant {label} evidence",
            ingestion_status="ready",
            created_by=identity.user_id,
        )
        session.add(source)
        session.flush()
        chunk = EvidenceChunk(
            workspace_id=identity.workspace_id,
            project_id=project.id,
            source_id=source.id,
            chunk_index=0,
            text=f"Tenant {label} evidence chunk",
            embedding=[0.1 if label == "A" else 0.2] * 1536,
        )
        memory = ProjectMemoryItem(
            workspace_id=identity.workspace_id,
            project_id=project.id,
            memory_type="project",
            status="active",
            write_policy="direct",
            title=f"RLS Memory {label}",
            summary=f"Tenant {label} memory",
            content={},
            provenance_metadata={},
            created_by=identity.user_id,
        )
        approval = ApprovalRequest(
            workspace_id=identity.workspace_id,
            project_id=project.id,
            request_type="tool_invocation",
            status="pending",
            requested_by="agent",
            risk_level="high",
            summary=f"Tenant {label} approval",
            proposed_change={},
        )
        tool_invocation = ToolInvocation(
            workspace_id=identity.workspace_id,
            project_id=project.id,
            tool_name="rls_test_tool",
            access_mode="proposal",
            risk_level="high",
            input_json={},
            status="requested",
            requested_by="agent",
        )
        decision = Decision(
            workspace_id=identity.workspace_id,
            project_id=project.id,
            decision_type="build",
            title=f"RLS Decision {label}",
            created_by=identity.user_id,
        )
        plan = ResearchPlan(
            workspace_id=identity.workspace_id,
            project_id=project.id,
            objective=f"RLS Research {label}",
            status="approved",
            created_by=identity.user_id,
        )
        session.add_all([chunk, memory, approval, tool_invocation, decision, plan])
        session.flush()
        sprint = ResearchSprint(
            workspace_id=identity.workspace_id,
            project_id=project.id,
            research_plan_id=plan.id,
            status="running",
            temporal_workflow_id=f"rls-workflow-{label}-{uuid.uuid4().hex}",
            temporal_run_id=f"rls-run-{label}-{uuid.uuid4().hex}",
            langsmith_trace_id=f"rls-trace-{label}-{uuid.uuid4().hex}",
            created_by=identity.user_id,
        )
        session.add(sprint)
        session.commit()
        return TenantRecords(
            project_id=project.id,
            source_id=source.id,
            chunk_id=chunk.id,
            memory_id=memory.id,
            approval_id=approval.id,
            tool_invocation_id=tool_invocation.id,
            decision_id=decision.id,
            sprint_id=sprint.id,
        )


def _delete_tenant_records(
    engine,
    identity: FixtureIdentity,
    records: TenantRecords,
) -> None:
    with Session(engine) as session:
        bind_tenant_context(session, identity)
        session.execute(delete(Project).where(Project.id == records.project_id))
        session.commit()


def _delete_identities(
    engine,
    *identities: FixtureIdentity,
) -> None:
    with Session(engine) as session:
        user_ids = [identity.user_id for identity in identities]
        workspace_ids = [identity.workspace_id for identity in identities]
        session.execute(delete(WorkspaceMember).where(WorkspaceMember.user_id.in_(user_ids)))
        session.execute(delete(Workspace).where(Workspace.id.in_(workspace_ids)))
        session.execute(delete(User).where(User.id.in_(user_ids)))
        session.commit()
