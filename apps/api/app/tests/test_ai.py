import json
import uuid
from decimal import Decimal

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ai.litellm_client import ChatMessage, LLMCompletion
from app.ai.structured_output import generate_structured_output
from app.core.config import get_settings
from app.db.models import AIRun, AIStep
from app.schemas.ai import LiteLLMReachabilityStatus, StructuredOutputSmokeResult


def test_structured_output_endpoint_uses_stub_and_logs_run(
    client: TestClient,
    db_session: Session,
) -> None:
    response = client.post(
        "/api/ai/test-structured-output",
        json={
            "idea": (
                "An AI platform for independent fitness coaches that summarizes check-ins "
                "and suggests adaptive training changes."
            )
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["used_stub"] is True
    assert body["model_provider"] == "stub"
    assert body["total_tokens"] > 0
    assert body["output"]["summary"].startswith("Deterministic summary for:")
    assert body["output"]["target_users"]
    assert body["output"]["confidence"] in ["low", "medium", "high"]

    run_id = uuid.UUID(body["ai_run_id"])
    step_id = uuid.UUID(body["ai_step_id"])

    run = db_session.scalar(select(AIRun).where(AIRun.id == run_id))
    assert run is not None
    assert run.workflow_type == "structured_output_smoke_test"
    assert run.status == "succeeded"
    assert run.total_tokens == body["total_tokens"]
    assert run.model_provider == "stub"
    assert run.prompt_version == body["prompt_version"]

    step = db_session.scalar(select(AIStep).where(AIStep.id == step_id))
    assert step is not None
    assert step.ai_run_id == run.id
    assert step.step_name == "structured_generation"
    assert step.status == "succeeded"
    assert step.output_json == body["output"]


def test_structured_output_project_id_is_workspace_scoped(client: TestClient) -> None:
    user_a_headers = {"X-Dev-User-Email": "a@example.com", "X-Dev-User-Name": "User A"}
    user_b_headers = {"X-Dev-User-Email": "b@example.com", "X-Dev-User-Name": "User B"}

    create_response = client.post(
        "/api/projects",
        headers=user_a_headers,
        json={"name": "Private project", "short_description": "Scoped project."},
    )
    assert create_response.status_code == 201
    project_id = create_response.json()["id"]

    response = client.post(
        "/api/ai/test-structured-output",
        headers=user_b_headers,
        json={"idea": "Analyze this", "project_id": project_id},
    )

    assert response.status_code == 404


def test_ai_status_reports_stub_mode_without_secret_values(
    client: TestClient,
    monkeypatch,
) -> None:
    monkeypatch.setenv("LITELLM_MODEL", "dev-gpt-4o-mini")
    monkeypatch.setenv("OPENAI_API_KEY", "")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "")
    monkeypatch.setenv("GEMINI_API_KEY", "")
    get_settings.cache_clear()
    monkeypatch.setattr(
        "app.routers.ai._check_litellm_reachability",
        lambda settings: LiteLLMReachabilityStatus(
            base_url=settings.litellm_base_url,
            endpoint=f"{settings.litellm_base_url}/health/liveliness",
            reachable=False,
            status_code=None,
            error="connection refused",
        ),
    )

    response = client.get("/api/ai/status")

    assert response.status_code == 200
    body = response.json()
    assert body["llm_stub_mode"] == "always"
    assert body["llm_fallback_policy"] == "emergency"
    assert body["llm_structured_output_repair_attempts"] == 1
    assert body["resolved_mode"] == "stub"
    assert body["should_use_stub"] is True
    assert body["litellm_model"] == "dev-gpt-4o-mini"
    assert body["provider_keys"] == {
        "openai": False,
        "anthropic": False,
        "gemini": False,
        "any_present": False,
    }
    assert body["litellm_reachability"]["reachable"] is False
    assert "sk-" not in response.text


def test_ai_status_reports_live_mode_when_stub_mode_is_never(
    client: TestClient,
    monkeypatch,
) -> None:
    monkeypatch.setenv("LLM_STUB_MODE", "never")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-provider-key")
    get_settings.cache_clear()
    monkeypatch.setattr(
        "app.routers.ai._check_litellm_reachability",
        lambda settings: LiteLLMReachabilityStatus(
            base_url=settings.litellm_base_url,
            endpoint=f"{settings.litellm_base_url}/health/liveliness",
            reachable=True,
            status_code=200,
            error=None,
        ),
    )

    response = client.get("/api/ai/status")

    assert response.status_code == 200
    body = response.json()
    assert body["llm_stub_mode"] == "never"
    assert body["resolved_mode"] == "live"
    assert body["should_use_stub"] is False
    assert body["provider_keys"]["openai"] is True
    assert body["provider_keys"]["any_present"] is True
    assert body["litellm_reachability"]["reachable"] is True
    assert "sk-test-provider-key" not in response.text


def test_structured_output_endpoint_uses_litellm_when_stub_mode_is_never(
    client: TestClient,
    monkeypatch,
) -> None:
    monkeypatch.setenv("LLM_STUB_MODE", "never")
    monkeypatch.setenv("LITELLM_MODEL", "dev-gpt-4o-mini")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-provider-key")
    get_settings.cache_clear()

    def fake_complete(
        self,
        messages,
        *,
        model=None,
        temperature=0.0,
        response_format_json=False,
        max_tokens=None,
    ):
        output = StructuredOutputSmokeResult(
            summary="Live model summary.",
            target_users=["Independent fitness coaches"],
            key_uncertainties=["Willingness to pay"],
            recommended_next_step="Run five discovery interviews.",
            confidence="medium",
        )
        return LLMCompletion(
            content=output.model_dump_json(),
            model_provider="litellm",
            model_name=model or "dev-gpt-4o-mini",
            prompt_tokens=10,
            completion_tokens=20,
            total_tokens=30,
            total_cost=Decimal("0.00042"),
            raw_response={"test": True},
            used_stub=False,
        )

    monkeypatch.setattr("app.ai.structured_output.LiteLLMClient.complete", fake_complete)

    response = client.post(
        "/api/ai/test-structured-output",
        json={"idea": "AI workspace for independent fitness coaches"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["used_stub"] is False
    assert body["model_provider"] == "litellm"
    assert body["model_name"] == "dev-gpt-4o-mini"
    assert body["total_tokens"] == 30
    assert body["total_cost"] == "0.00042"


def test_structured_output_accepts_single_schema_wrapper(monkeypatch) -> None:
    monkeypatch.setenv("LLM_STUB_MODE", "never")
    get_settings.cache_clear()
    output = StructuredOutputSmokeResult(
        summary="Wrapped live model summary.",
        target_users=["Independent fitness coaches"],
        key_uncertainties=["Willingness to pay"],
        recommended_next_step="Run five discovery interviews.",
        confidence="medium",
    )

    def fake_complete(
        self,
        messages,
        *,
        model=None,
        temperature=0.0,
        response_format_json=False,
        max_tokens=None,
    ):
        wrapped_content = {
            "structuredOutputSmokeResult": {
                "summary": output.summary,
                "targetUsers": output.target_users,
                "keyUncertainties": output.key_uncertainties,
                "recommendedNextStep": output.recommended_next_step,
                "confidence": output.confidence,
            }
        }
        return LLMCompletion(
            content=json.dumps(wrapped_content),
            model_provider="litellm",
            model_name=model or "dev-gpt-4o-mini",
            prompt_tokens=10,
            completion_tokens=20,
            total_tokens=30,
            total_cost=Decimal("0.00042"),
            raw_response={"test": True},
            used_stub=False,
        )

    monkeypatch.setattr("app.ai.structured_output.LiteLLMClient.complete", fake_complete)

    result = generate_structured_output(
        get_settings(),
        StructuredOutputSmokeResult,
        [ChatMessage(role="user", content="Analyze this idea.")],
    )

    assert result.parsed.summary == "Wrapped live model summary."


def test_structured_output_repairs_invalid_model_json(monkeypatch) -> None:
    monkeypatch.setenv("LLM_STUB_MODE", "never")
    monkeypatch.setenv("LLM_STRUCTURED_OUTPUT_REPAIR_ATTEMPTS", "1")
    get_settings.cache_clear()
    calls = {"count": 0}
    output = StructuredOutputSmokeResult(
        summary="Repaired live model summary.",
        target_users=["Independent fitness coaches"],
        key_uncertainties=["Willingness to pay"],
        recommended_next_step="Run five discovery interviews.",
        confidence="medium",
    )

    def fake_complete(
        self,
        messages,
        *,
        model=None,
        temperature=0.0,
        response_format_json=False,
        max_tokens=None,
    ):
        calls["count"] += 1
        content = (
            json.dumps({"summary": "Missing required fields."})
            if calls["count"] == 1
            else output.model_dump_json()
        )
        return LLMCompletion(
            content=content,
            model_provider="litellm",
            model_name=model or "dev-gpt-4o-mini",
            prompt_tokens=10,
            completion_tokens=20,
            total_tokens=30,
            total_cost=Decimal("0.00042"),
            raw_response={"attempt": calls["count"]},
            used_stub=False,
        )

    monkeypatch.setattr("app.ai.structured_output.LiteLLMClient.complete", fake_complete)

    result = generate_structured_output(
        get_settings(),
        StructuredOutputSmokeResult,
        [ChatMessage(role="user", content="Analyze this idea.")],
    )

    assert calls["count"] == 2
    assert result.parsed.summary == "Repaired live model summary."
    assert result.completion.model_provider == "litellm"
    assert result.completion.used_stub is False
    assert result.completion.total_tokens == 60
    assert result.completion.raw_response["attempt_count"] == 2
