import asyncio
from pathlib import Path
from types import SimpleNamespace

import pytest
import yaml
from google.protobuf.duration_pb2 import Duration
from pydantic import ValidationError
from temporalio.api.namespace.v1.message_pb2 import NamespaceConfig

from app.core.config import Settings
from app.services import retention_provider_service

REPO_ROOT = Path(__file__).resolve().parents[5]


def test_langsmith_tracing_requires_matching_provider_retention_attestation() -> None:
    with pytest.raises(ValidationError, match="LANGSMITH_PROVIDER_RETENTION_DAYS"):
        Settings(langsmith_tracing=True)

    settings = Settings(
        langsmith_tracing=True,
        langsmith_provider_retention_days=14,
    )
    assert settings.langsmith_provider_retention_days == settings.retention_langsmith_trace_days

    with pytest.raises(ValidationError, match="LANGSMITH_PROVIDER_RETENTION_DAYS"):
        Settings(langsmith_tracing=True, langsmith_provider_retention_days=15)


def test_temporal_namespace_retention_is_reconciled_when_ttl_differs() -> None:
    service = _WorkflowService(current_seconds=3 * 24 * 60 * 60)
    settings = Settings(
        temporal_namespace="retention-test",
        temporal_namespace_retention_reconcile_enabled=True,
        retention_temporal_history_days=30,
    )

    asyncio.run(
        retention_provider_service.ensure_temporal_namespace_retention(
            _TemporalClient(service),
            settings,
        )
    )

    assert service.update_request is not None
    assert service.update_request.namespace == "retention-test"
    assert (
        service.update_request.config.workflow_execution_retention_ttl.seconds
        == 30 * 24 * 60 * 60
    )


def test_temporal_namespace_retention_skips_matching_or_disabled_configuration() -> None:
    matching_service = _WorkflowService(current_seconds=30 * 24 * 60 * 60)
    enabled_settings = Settings(temporal_namespace_retention_reconcile_enabled=True)
    asyncio.run(
        retention_provider_service.ensure_temporal_namespace_retention(
            _TemporalClient(matching_service),
            enabled_settings,
        )
    )
    assert matching_service.update_request is None

    disabled_service = _WorkflowService(current_seconds=1)
    asyncio.run(
        retention_provider_service.ensure_temporal_namespace_retention(
            _TemporalClient(disabled_service),
            Settings(),
        )
    )
    assert disabled_service.describe_calls == 0


def test_compose_declares_provider_retention_for_all_trace_producers() -> None:
    compose = yaml.safe_load((REPO_ROOT / "docker-compose.yml").read_text())
    api_environment = compose["services"]["api"]["environment"]
    worker_environment = compose["services"]["temporal-worker"]["environment"]

    assert api_environment["LANGSMITH_PROVIDER_RETENTION_DAYS"].endswith(":-14}")
    assert worker_environment["LANGSMITH_PROVIDER_RETENTION_DAYS"].endswith(":-14}")
    assert worker_environment["TEMPORAL_NAMESPACE_RETENTION_RECONCILE_ENABLED"].endswith(
        ":-true}"
    )


class _TemporalClient:
    def __init__(self, workflow_service: "_WorkflowService") -> None:
        self.workflow_service = workflow_service


class _WorkflowService:
    def __init__(self, *, current_seconds: int) -> None:
        self.current_seconds = current_seconds
        self.describe_calls = 0
        self.update_request = None

    async def describe_namespace(self, _request):
        self.describe_calls += 1
        return SimpleNamespace(
            config=NamespaceConfig(
                workflow_execution_retention_ttl=Duration(seconds=self.current_seconds)
            )
        )

    async def update_namespace(self, request) -> None:
        self.update_request = request
