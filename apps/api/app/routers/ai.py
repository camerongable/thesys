from time import perf_counter
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.ai.litellm_client import ChatMessage
from app.ai.prompts import STRUCTURED_OUTPUT_SMOKE_TEST_PROMPT_VERSION
from app.ai.structured_output import StructuredOutputError, generate_structured_output
from app.core.auth import AuthContextDep, SettingsDep
from app.db.session import get_db
from app.schemas.ai import (
    StructuredOutputSmokeResult,
    StructuredOutputTestCreate,
    StructuredOutputTestRead,
)
from app.services import ai_run_service, project_service

router = APIRouter(prefix="/api/ai", tags=["ai"])
DbDep = Annotated[Session, Depends(get_db)]


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
            detail="Structured output generation failed.",
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
