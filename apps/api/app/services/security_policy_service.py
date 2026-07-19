"""Rate, concurrency, budget, and provider-egress guards for expensive workflows."""

import ipaddress
import time
import uuid
from collections import defaultdict, deque
from collections.abc import Generator, Iterable
from contextlib import contextmanager
from dataclasses import dataclass
from decimal import Decimal
from threading import RLock
from urllib.parse import urlparse

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.core.auth import AuthContext
from app.core.config import Settings
from app.services import ai_accounting_service, governance_service, kill_switch_service


class ProviderEgressDeniedError(RuntimeError):
    """Raised when a configured live provider endpoint is outside policy."""


@dataclass(frozen=True)
class WorkflowBudgetEstimate:
    """Pre-call exposure estimate used before model/search/extraction work starts."""

    estimated_tokens: int
    estimated_cost: Decimal
    provider_urls: tuple[str, ...] = ()


_rate_events: dict[tuple[str, str, str], deque[float]] = defaultdict(deque)
_concurrency_counts: dict[tuple[str, str], int] = defaultdict(int)
_lock = RLock()


def default_budget_estimate(
    settings: Settings,
    *,
    multiplier: float = 1.0,
) -> WorkflowBudgetEstimate:
    """Return a conservative default estimate for route-level preflight checks."""
    tokens = max(1, int(settings.ai_workflow_default_estimated_tokens * multiplier))
    cost = Decimal(str(settings.ai_workflow_default_estimated_cost_usd)) * Decimal(str(multiplier))
    return WorkflowBudgetEstimate(estimated_tokens=tokens, estimated_cost=cost)


def llm_provider_urls(settings: Settings) -> tuple[str, ...]:
    """Return configured LLM egress targets when live model calls may occur."""
    return () if settings.should_use_llm_stub else (settings.litellm_base_url,)


def embedding_provider_urls(settings: Settings) -> tuple[str, ...]:
    """Return configured embedding provider egress targets."""
    return (settings.litellm_base_url,) if settings.embedding_provider == "litellm" else ()


def search_provider_urls(settings: Settings) -> tuple[str, ...]:
    """Return configured external-search egress targets."""
    if settings.external_search_enabled and settings.external_search_provider == "tavily":
        return ("https://api.tavily.com",)
    return ()


def multimodal_provider_urls(settings: Settings) -> tuple[str, ...]:
    """Return configured multimodal extraction egress targets."""
    if settings.multimodal_extraction_provider == "litellm":
        return (settings.litellm_base_url,)
    return ()


def merge_estimate(
    settings: Settings,
    *,
    multiplier: float = 1.0,
    provider_urls: Iterable[str] = (),
) -> WorkflowBudgetEstimate:
    """Build a default estimate and attach live provider targets."""
    base = default_budget_estimate(settings, multiplier=multiplier)
    return WorkflowBudgetEstimate(
        estimated_tokens=base.estimated_tokens,
        estimated_cost=base.estimated_cost,
        provider_urls=tuple(dict.fromkeys(provider_urls)),
    )


@contextmanager
def guarded_workflow(
    db: Session,
    auth: AuthContext,
    settings: Settings,
    *,
    project_id: uuid.UUID | None,
    workflow_type: str,
    estimate: WorkflowBudgetEstimate | None = None,
) -> Generator[None, None, None]:
    """Apply route-level rate, concurrency, budget, and egress policy."""
    estimate = estimate or default_budget_estimate(settings)
    acquired = False
    try:
        _enforce_runtime_kill_switches(db, auth, settings, estimate)
        _enforce_rate_limits(settings, auth, workflow_type)
        _acquire_concurrency(settings, auth, workflow_type)
        acquired = True
        if project_id is not None:
            ai_accounting_service.assert_project_budget_available(
                db,
                auth,
                settings,
                project_id,
                estimated_tokens=estimate.estimated_tokens,
                estimated_cost=estimate.estimated_cost,
            )
        for provider_url in estimate.provider_urls:
            try:
                enforce_provider_egress_policy(settings, provider_url)
            except ProviderEgressDeniedError as exc:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=str(exc),
                ) from exc
        yield
    except HTTPException as exc:
        if _is_policy_denial(exc):
            _record_policy_denial(
                db,
                auth,
                project_id=project_id,
                workflow_type=workflow_type,
                status_code=exc.status_code,
                detail=str(exc.detail),
            )
        raise
    finally:
        if acquired:
            _release_concurrency(auth, workflow_type)


def enforce_provider_egress_policy(settings: Settings, url: str) -> None:
    """Fail closed when a live provider endpoint is not explicitly allowlisted."""
    if not settings.provider_egress_policy_enabled:
        return
    parsed = urlparse(url)
    if parsed.scheme.casefold() not in {"http", "https"} or not parsed.hostname:
        raise ProviderEgressDeniedError("Provider endpoint must be an http(s) URL with a host.")

    host = parsed.hostname.strip("[]").casefold()
    allowed_hosts = [item.strip().casefold() for item in settings.provider_egress_allowed_hosts]
    if not any(_host_matches(host, allowed_host) for allowed_host in allowed_hosts):
        raise ProviderEgressDeniedError(f"Provider host is not allowlisted: {host}.")


def _enforce_runtime_kill_switches(
    db: Session,
    auth: AuthContext,
    settings: Settings,
    estimate: WorkflowBudgetEstimate,
) -> None:
    if kill_switch_service.is_enabled(db, auth, settings, "disable_model_provider") and any(
        _is_model_provider_url(settings, url) for url in estimate.provider_urls
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Model-provider access is temporarily unavailable.",
        )
    if kill_switch_service.is_enabled(db, auth, settings, "disable_external_egress") and any(
        _is_external_network_target(url) for url in estimate.provider_urls
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="External network access is temporarily unavailable.",
        )


def enforce_source_fetching_allowed(
    db: Session,
    auth: AuthContext,
    settings: Settings,
    *,
    project_id: uuid.UUID | None,
    workflow_type: str,
) -> None:
    if not kill_switch_service.is_enabled(db, auth, settings, "disable_source_fetching"):
        return
    detail = "Source fetching is temporarily unavailable."
    _record_policy_denial(
        db,
        auth,
        project_id=project_id,
        workflow_type=workflow_type,
        status_code=status.HTTP_403_FORBIDDEN,
        detail=detail,
    )
    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=detail)


def enforce_memory_writes_allowed(
    db: Session,
    auth: AuthContext,
    settings: Settings,
    *,
    project_id: uuid.UUID,
    operation: str,
) -> None:
    if not kill_switch_service.is_enabled(db, auth, settings, "disable_memory_writes"):
        return
    detail = "Memory updates are temporarily unavailable."
    _record_policy_denial(
        db,
        auth,
        project_id=project_id,
        workflow_type=f"memory_{operation}",
        status_code=status.HTTP_403_FORBIDDEN,
        detail=detail,
    )
    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=detail)


def enforce_agent_writes_allowed(
    db: Session,
    auth: AuthContext,
    settings: Settings,
    *,
    project_id: uuid.UUID,
    operation: str,
) -> None:
    if not kill_switch_service.is_enabled(db, auth, settings, "disable_all_agent_writes"):
        return
    detail = "Agent-initiated updates are temporarily unavailable."
    _record_policy_denial(
        db,
        auth,
        project_id=project_id,
        workflow_type=f"agent_write_{operation}",
        status_code=status.HTTP_403_FORBIDDEN,
        detail=detail,
    )
    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=detail)


def enforce_external_mcp_allowed(
    db: Session,
    auth: AuthContext,
    settings: Settings,
    *,
    project_id: uuid.UUID | None = None,
    operation: str,
) -> None:
    if not kill_switch_service.is_enabled(db, auth, settings, "disable_external_mcp"):
        return
    detail = "External MCP access is temporarily unavailable."
    _record_policy_denial(
        db,
        auth,
        project_id=project_id,
        workflow_type=f"external_mcp_{operation}",
        status_code=status.HTTP_403_FORBIDDEN,
        detail=detail,
    )
    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=detail)


def _is_model_provider_url(settings: Settings, url: str) -> bool:
    return url.rstrip("/") == settings.litellm_base_url.rstrip("/")


def _is_external_network_target(url: str) -> bool:
    host = urlparse(url).hostname
    if host is None:
        return False
    normalized = host.strip("[]").casefold()
    if normalized in {"localhost", "localhost.localdomain"}:
        return False
    try:
        return not ipaddress.ip_address(normalized).is_loopback
    except ValueError:
        return True


def reset_policy_state() -> None:
    """Clear in-memory limiter state for tests and local development resets."""
    with _lock:
        _rate_events.clear()
        _concurrency_counts.clear()


def _enforce_rate_limits(settings: Settings, auth: AuthContext, workflow_type: str) -> None:
    if not settings.security_rate_limit_enabled:
        return
    now = time.monotonic()
    window = float(settings.security_rate_limit_window_seconds)
    with _lock:
        _check_rate_bucket(
            key=("user", str(auth.user_id), workflow_type),
            now=now,
            window=window,
            max_requests=settings.security_rate_limit_user_max_requests,
            detail="Per-user expensive workflow rate limit exceeded.",
        )
        _check_rate_bucket(
            key=("workspace", str(auth.workspace_id), workflow_type),
            now=now,
            window=window,
            max_requests=settings.security_rate_limit_workspace_max_requests,
            detail="Per-workspace expensive workflow rate limit exceeded.",
        )


def _check_rate_bucket(
    *,
    key: tuple[str, str, str],
    now: float,
    window: float,
    max_requests: int,
    detail: str,
) -> None:
    events = _rate_events[key]
    while events and now - events[0] > window:
        events.popleft()
    if len(events) >= max_requests:
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail=detail)
    events.append(now)


def _acquire_concurrency(settings: Settings, auth: AuthContext, workflow_type: str) -> None:
    with _lock:
        for key in _concurrency_keys(auth, workflow_type):
            if _concurrency_counts[key] >= settings.security_max_concurrent_workflows:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Expensive workflow concurrency limit exceeded.",
                )
        for key in _concurrency_keys(auth, workflow_type):
            _concurrency_counts[key] += 1


def _release_concurrency(auth: AuthContext, workflow_type: str) -> None:
    with _lock:
        for key in _concurrency_keys(auth, workflow_type):
            _concurrency_counts[key] = max(0, _concurrency_counts[key] - 1)


def _concurrency_keys(auth: AuthContext, workflow_type: str) -> tuple[tuple[str, str], ...]:
    return (
        (f"user:{auth.user_id}", workflow_type),
        (f"workspace:{auth.workspace_id}", workflow_type),
    )


def _is_policy_denial(exc: HTTPException) -> bool:
    return exc.status_code in {
        status.HTTP_402_PAYMENT_REQUIRED,
        status.HTTP_403_FORBIDDEN,
        status.HTTP_409_CONFLICT,
        status.HTTP_429_TOO_MANY_REQUESTS,
    }


def _record_policy_denial(
    db: Session,
    auth: AuthContext,
    *,
    project_id: uuid.UUID | None,
    workflow_type: str,
    status_code: int,
    detail: str,
) -> None:
    governance_service.record_audit_event(
        db,
        auth,
        event_type="security_policy_denied",
        actor_type="user",
        project_id=project_id,
        summary=f"Denied {workflow_type} before the guarded operation started.",
        risk_level="medium",
        metadata={
            "workflow_type": workflow_type,
            "status_code": status_code,
            "detail": detail,
        },
    )
    db.commit()


def _host_matches(host: str, policy: str) -> bool:
    if not policy:
        return False
    if policy.startswith("*."):
        suffix = policy[1:]
        return host.endswith(suffix)
    if policy.startswith("."):
        return host.endswith(policy)
    if host == policy:
        return True
    try:
        return ipaddress.ip_address(host) == ipaddress.ip_address(policy)
    except ValueError:
        return False
