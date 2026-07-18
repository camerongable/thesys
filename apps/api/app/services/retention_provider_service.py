"""Provider-owned retention configuration checks and Temporal reconciliation."""

from google.protobuf.duration_pb2 import Duration
from temporalio.api.namespace.v1.message_pb2 import NamespaceConfig
from temporalio.api.workflowservice.v1.request_response_pb2 import (
    DescribeNamespaceRequest,
    UpdateNamespaceRequest,
)
from temporalio.client import Client

from app.core.config import Settings


async def ensure_temporal_namespace_retention(client: Client, settings: Settings) -> None:
    """Set Temporal history retention to the configured policy when enabled."""
    if not settings.temporal_namespace_retention_reconcile_enabled:
        return
    desired_seconds = settings.retention_temporal_history_days * 24 * 60 * 60
    response = await client.workflow_service.describe_namespace(
        DescribeNamespaceRequest(namespace=settings.temporal_namespace)
    )
    current_seconds = response.config.workflow_execution_retention_ttl.seconds
    if current_seconds == desired_seconds:
        return
    await client.workflow_service.update_namespace(
        UpdateNamespaceRequest(
            namespace=settings.temporal_namespace,
            config=NamespaceConfig(
                workflow_execution_retention_ttl=Duration(seconds=desired_seconds)
            ),
        )
    )
