import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.auth import AuthContextDep
from app.db.models import ToolInvocation
from app.db.session import get_db
from app.schemas.tools import (
    AgentToolDefinitionRead,
    ToolInvocationActionRead,
    ToolInvocationListRead,
    ToolInvocationRead,
    ToolRegistryRead,
)
from app.services import tool_service

router = APIRouter(tags=["tools"])
DbDep = Annotated[Session, Depends(get_db)]
ResearchSprintIdQuery = Annotated[uuid.UUID | None, Query()]
LimitQuery = Annotated[int, Query(ge=1, le=100)]


def serialize_tool_definition(definition: tool_service.ToolDefinition) -> AgentToolDefinitionRead:
    return AgentToolDefinitionRead(
        name=definition.name,
        title=definition.title,
        description=definition.description,
        input_schema=definition.input_schema,
        output_schema=definition.output_schema,
        access_mode=definition.access_mode,
        risk_level=definition.risk_level,
        approval_policy=definition.approval_policy,
        allowed_project_roles=definition.allowed_project_roles,
    )


def serialize_invocation(invocation: ToolInvocation) -> ToolInvocationRead:
    return ToolInvocationRead.model_validate(invocation)


@router.get("/api/tools", response_model=ToolRegistryRead)
def list_tools() -> ToolRegistryRead:
    return ToolRegistryRead(
        tools=[
            serialize_tool_definition(definition)
            for definition in tool_service.list_tool_definitions()
        ]
    )


@router.get(
    "/api/projects/{project_id}/tool-invocations",
    response_model=ToolInvocationListRead,
)
def list_project_tool_invocations(
    project_id: uuid.UUID,
    db: DbDep,
    auth: AuthContextDep,
    research_sprint_id: ResearchSprintIdQuery = None,
    limit: LimitQuery = 50,
) -> ToolInvocationListRead:
    invocations = tool_service.list_tool_invocations(
        db,
        auth,
        project_id,
        research_sprint_id=research_sprint_id,
        limit=limit,
    )
    return ToolInvocationListRead(
        invocations=[serialize_invocation(item) for item in invocations]
    )


@router.post(
    "/api/projects/{project_id}/tool-invocations/{invocation_id}/approve",
    response_model=ToolInvocationActionRead,
)
def approve_project_tool_invocation(
    project_id: uuid.UUID,
    invocation_id: uuid.UUID,
    db: DbDep,
    auth: AuthContextDep,
) -> ToolInvocationActionRead:
    invocation = tool_service.approve_tool_invocation(db, auth, project_id, invocation_id)
    return ToolInvocationActionRead(invocation=serialize_invocation(invocation))


@router.post(
    "/api/projects/{project_id}/tool-invocations/{invocation_id}/reject",
    response_model=ToolInvocationActionRead,
)
def reject_project_tool_invocation(
    project_id: uuid.UUID,
    invocation_id: uuid.UUID,
    db: DbDep,
    auth: AuthContextDep,
) -> ToolInvocationActionRead:
    invocation = tool_service.reject_tool_invocation(db, auth, project_id, invocation_id)
    return ToolInvocationActionRead(invocation=serialize_invocation(invocation))
