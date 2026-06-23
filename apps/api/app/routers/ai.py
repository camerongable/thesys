from time import perf_counter
from typing import Annotated

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.ai.litellm_client import ChatMessage
from app.ai.prompts import STRUCTURED_OUTPUT_SMOKE_TEST_PROMPT_VERSION
from app.ai.structured_output import StructuredOutputError, generate_structured_output
from app.core.auth import AuthContextDep, SettingsDep
from app.core.config import Settings
from app.core.errors import public_error_detail
from app.db.session import get_db
from app.schemas.ai import (
    AIProviderKeyStatus,
    AIStatusRead,
    AIStatusStructuredOutputCheck,
    LiteLLMReachabilityStatus,
    StructuredOutputSmokeResult,
    StructuredOutputTestCreate,
    StructuredOutputTestRead,
)
from app.services import ai_run_service, project_service

router = APIRouter(prefix="/api/ai", tags=["ai"])
DbDep = Annotated[Session, Depends(get_db)]
HealthcheckQuery = Annotated[bool, Query(description="Run a small structured-output check.")]


@router.get("/status", response_model=AIStatusRead)
def get_ai_status(
    _auth: AuthContextDep,
    settings: SettingsDep,
    include_structured_output_check: HealthcheckQuery = False,
) -> AIStatusRead:
    provider_keys = _provider_key_status(settings)
    return AIStatusRead(
        llm_stub_mode=settings.llm_stub_mode,
        llm_fallback_policy=settings.llm_fallback_policy,
        llm_structured_output_repair_attempts=settings.llm_structured_output_repair_attempts,
        resolved_mode="stub" if settings.should_use_llm_stub else "live",
        should_use_stub=settings.should_use_llm_stub,
        litellm_model=settings.litellm_model,
        litellm_base_url=settings.litellm_base_url,
        litellm_reachability=_check_litellm_reachability(settings),
        provider_keys=provider_keys,
        embedding_provider=settings.embedding_provider,
        embedding_model=settings.embedding_model,
        embedding_dimension=settings.embedding_dimension,
        embedding_version=settings.embedding_version,
        embedding_timeout_seconds=settings.embedding_timeout_seconds,
        embedding_retry_attempts=settings.embedding_retry_attempts,
        retrieval_vector_path=settings.retrieval_vector_path,
        retrieval_python_fallback_enabled=settings.retrieval_python_fallback_enabled,
        retrieval_reranking_enabled=settings.retrieval_reranking_enabled,
        retrieval_reranker_provider=settings.retrieval_reranker_provider,
        retrieval_context_token_budget=settings.retrieval_context_token_budget,
        retrieval_max_chunks_per_source=settings.retrieval_max_chunks_per_source,
        retrieval_min_context_score=settings.retrieval_min_context_score,
        external_search_enabled=settings.external_search_enabled,
        external_search_provider=settings.external_search_provider,
        external_search_max_results_per_query=settings.external_search_max_results_per_query,
        external_search_max_queries_per_sprint=settings.external_search_max_queries_per_sprint,
        multimodal_extraction_provider=settings.multimodal_extraction_provider,
        multimodal_extraction_model=settings.multimodal_extraction_model,
        multimodal_pdf_fallback_enabled=settings.multimodal_pdf_fallback_enabled,
        multimodal_pdf_min_text_chars=settings.multimodal_pdf_min_text_chars,
        structured_output_healthcheck=(
            _run_structured_output_healthcheck(settings)
            if include_structured_output_check
            else None
        ),
    )


@router.post("/test-structured-output", response_model=StructuredOutputTestRead)
def test_structured_output(
    payload: StructuredOutputTestCreate,
    db: DbDep,
    auth: AuthContextDep,
    settings: SettingsDep,
) -> StructuredOutputTestRead:
    project_id = payload.project_id
    if project_id is not None:
        project_service.get_project(db, auth, project_id)

    input_summary = payload.idea.strip()[:500]
    run = ai_run_service.start_run(
        db,
        auth,
        workflow_type="structured_output_smoke_test",
        prompt_version=STRUCTURED_OUTPUT_SMOKE_TEST_PROMPT_VERSION,
        input_summary=input_summary,
        project_id=project_id,
        model_provider="stub" if settings.should_use_llm_stub else "litellm",
        model_name=settings.litellm_model,
    )
    messages = [
        ChatMessage(
            role="system",
            content=(
                "You extract a concise strategic summary. Be direct, skeptical, and specific. "
                "Return only the requested structured fields."
            ),
        ),
        ChatMessage(
            role="user",
            content=f"Analyze this rough founder idea for a smoke test: {payload.idea.strip()}",
        ),
    ]
    step = ai_run_service.start_step(
        db,
        run,
        step_name="structured_generation",
        input_json={
            "schema": StructuredOutputSmokeResult.__name__,
            "messages": [message.model_dump() for message in messages],
        },
    )

    started = perf_counter()
    try:
        result = generate_structured_output(
            settings,
            StructuredOutputSmokeResult,
            messages,
            model=settings.litellm_model,
            temperature=0.0,
        )
    except (StructuredOutputError, RuntimeError) as exc:
        latency_ms = int((perf_counter() - started) * 1000)
        ai_run_service.fail_step(db, step, error=str(exc), latency_ms=latency_ms)
        ai_run_service.fail_run(db, run, error=str(exc))
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=public_error_detail("Structured output generation failed.", exc),
        ) from exc

    latency_ms = int((perf_counter() - started) * 1000)
    output_json = result.parsed.model_dump(mode="json")
    step = ai_run_service.complete_step(
        db,
        step,
        output_json=output_json,
        latency_ms=latency_ms,
        tokens=result.completion.total_tokens,
        cost=result.completion.total_cost,
    )
    run = ai_run_service.complete_run(
        db,
        run,
        output_summary=result.parsed.summary,
        total_tokens=result.completion.total_tokens,
        total_cost=result.completion.total_cost,
        model_provider=result.completion.model_provider,
        model_name=result.completion.model_name,
    )

    return StructuredOutputTestRead(
        ai_run_id=run.id,
        ai_step_id=step.id,
        prompt_version=STRUCTURED_OUTPUT_SMOKE_TEST_PROMPT_VERSION,
        model_provider=result.completion.model_provider,
        model_name=result.completion.model_name,
        used_stub=result.completion.used_stub,
        total_tokens=result.completion.total_tokens,
        total_cost=result.completion.total_cost,
        output=StructuredOutputSmokeResult.model_validate(result.parsed),
    )


def _provider_key_status(settings: Settings) -> AIProviderKeyStatus:
    openai = _has_secret(settings.openai_api_key)
    anthropic = _has_secret(settings.anthropic_api_key)
    gemini = _has_secret(settings.gemini_api_key)
    return AIProviderKeyStatus(
        openai=openai,
        anthropic=anthropic,
        gemini=gemini,
        any_present=openai or anthropic or gemini,
    )


def _has_secret(value: str | None) -> bool:
    return bool(value and value.strip())


def _check_litellm_reachability(settings: Settings) -> LiteLLMReachabilityStatus:
    base_url = settings.litellm_base_url.rstrip("/")
    endpoint = f"{base_url}/health/liveliness"
    headers = {"Authorization": f"Bearer {settings.litellm_api_key}"}
    try:
        with httpx.Client(timeout=min(settings.litellm_timeout_seconds, 3.0)) as client:
            response = client.get(endpoint, headers=headers)
        return LiteLLMReachabilityStatus(
            base_url=settings.litellm_base_url,
            endpoint=endpoint,
            reachable=True,
            status_code=response.status_code,
            error=None if response.status_code < 500 else response.text[:300],
        )
    except httpx.HTTPError as exc:
        return LiteLLMReachabilityStatus(
            base_url=settings.litellm_base_url,
            endpoint=endpoint,
            reachable=False,
            status_code=None,
            error=str(exc),
        )


def _run_structured_output_healthcheck(settings: Settings) -> AIStatusStructuredOutputCheck:
    messages = [
        ChatMessage(
            role="system",
            content="Return a concise JSON healthcheck for the configured model.",
        ),
        ChatMessage(
            role="user",
            content="Summarize this product idea in one sentence: AI workspace for founders.",
        ),
    ]
    try:
        result = generate_structured_output(
            settings,
            StructuredOutputSmokeResult,
            messages,
            model=settings.litellm_model,
            temperature=0.0,
        )
    except (StructuredOutputError, RuntimeError) as exc:
        return AIStatusStructuredOutputCheck(
            ok=False,
            used_stub=None,
            model_provider=None,
            model_name=None,
            total_tokens=None,
            total_cost=None,
            error=public_error_detail("Structured output healthcheck failed.", exc),
        )

    return AIStatusStructuredOutputCheck(
        ok=True,
        used_stub=result.completion.used_stub,
        model_provider=result.completion.model_provider,
        model_name=result.completion.model_name,
        total_tokens=result.completion.total_tokens,
        total_cost=result.completion.total_cost,
        error=None,
    )
