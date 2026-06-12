import json
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from time import perf_counter
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.ai.fallback_policy import (
    should_use_fallback_after_error,
    should_use_fallback_without_model,
)
from app.ai.litellm_client import ChatMessage, LLMCompletion
from app.ai.prompts import (
    COMPETITOR_ANALYSIS_PROMPT_VERSION,
    UNTRUSTED_RETRIEVED_CONTENT_RULE,
)
from app.ai.structured_output import StructuredOutputError, generate_structured_output
from app.core.auth import AuthContext, require_permission
from app.core.config import Settings
from app.db.models import (
    AIRun,
    AIStep,
    Artifact,
    ArtifactVersion,
    Claim,
    ClaimEvidenceLink,
    Competitor,
    CompetitorEvidenceLink,
    EvidenceChunk,
    EvidenceSource,
    Project,
)
from app.schemas.artifacts import Citation, ClaimDraft
from app.schemas.competitors import (
    CompetitorAnalysisDraft,
    CompetitorAnalyzeCreate,
    CompetitorClusterDraft,
    CompetitorCreate,
    CompetitorProfileDraft,
    CompetitorUpdate,
)
from app.schemas.evidence import EvidenceRetrieveCreate, EvidenceUrlCreate
from app.services import ai_run_service, evidence_service, project_service, retrieval_service


class CompetitorAnalysisError(RuntimeError):
    pass


COMPETITOR_RETRIEVAL_TOP_K = 5
COMPETITOR_EVIDENCE_TEXT_LIMIT = 700
COMPETITOR_MAX_TOKENS = 1000


@dataclass(frozen=True)
class CompetitorAnalysisResult:
    run: AIRun
    step: AIStep
    artifact: Artifact
    competitors: list[Competitor]
    claims: list[Claim]
    citations: list[Citation]
    unsupported_claims: list[str]
    retrieval_result_count: int
    ingested_source_count: int
    model_provider: str
    model_name: str
    used_stub: bool
    total_tokens: int | None
    total_cost: Decimal | None


def list_competitors(db: Session, auth: AuthContext, project_id: uuid.UUID) -> list[Competitor]:
    project_service.get_project(db, auth, project_id)
    return list(
        db.scalars(
            select(Competitor)
            .where(
                Competitor.workspace_id == auth.workspace_id,
                Competitor.project_id == project_id,
            )
            .options(selectinload(Competitor.evidence_links))
            .order_by(Competitor.updated_at.desc(), Competitor.name)
        )
    )


def get_competitor(
    db: Session,
    auth: AuthContext,
    project_id: uuid.UUID,
    competitor_id: uuid.UUID,
) -> Competitor:
    competitor = db.scalar(
        select(Competitor)
        .where(
            Competitor.id == competitor_id,
            Competitor.workspace_id == auth.workspace_id,
            Competitor.project_id == project_id,
        )
        .options(selectinload(Competitor.evidence_links))
    )
    if competitor is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Competitor not found.")
    return competitor


def create_competitor(
    db: Session,
    auth: AuthContext,
    project_id: uuid.UUID,
    payload: CompetitorCreate,
) -> Competitor:
    require_permission(auth, "run_research")
    project_service.get_project(db, auth, project_id)
    competitor = _find_existing_competitor(
        db,
        auth,
        project_id,
        payload.name,
        _url_text(payload.url),
    )
    if competitor is None:
        competitor = Competitor(
            workspace_id=auth.workspace_id,
            project_id=project_id,
            name=payload.name.strip(),
            url=_url_text(payload.url),
            category=payload.category,
            threat_level="unknown",
        )
        db.add(competitor)
    else:
        competitor.name = payload.name.strip()
        competitor.url = _url_text(payload.url) or competitor.url
        competitor.category = payload.category
    db.commit()
    return get_competitor(db, auth, project_id, competitor.id)


def update_competitor(
    db: Session,
    auth: AuthContext,
    project_id: uuid.UUID,
    competitor_id: uuid.UUID,
    payload: CompetitorUpdate,
) -> Competitor:
    require_permission(auth, "run_research")
    competitor = get_competitor(db, auth, project_id, competitor_id)
    update_data = payload.model_dump(exclude_unset=True)
    if "name" in update_data and update_data["name"] is not None:
        competitor.name = update_data["name"].strip()
    if "url" in update_data:
        competitor.url = _url_text(payload.url)
    for field in (
        "category",
        "target_user",
        "positioning",
        "pricing_summary",
        "key_features",
        "strengths",
        "weaknesses",
        "differentiation_notes",
        "threat_level",
        "watchlist_status",
    ):
        if field in update_data:
            value = update_data[field]
            if field == "key_features":
                competitor.key_features = value or []
            elif field in {"category", "threat_level", "watchlist_status"} and value is None:
                continue
            else:
                setattr(competitor, field, value)
    db.commit()
    return get_competitor(db, auth, project_id, competitor.id)


def analyze_competitors(
    db: Session,
    auth: AuthContext,
    settings: Settings,
    project_id: uuid.UUID,
    payload: CompetitorAnalyzeCreate,
) -> CompetitorAnalysisResult:
    require_permission(auth, "run_research")
    project = project_service.get_project(db, auth, project_id)
    run = ai_run_service.start_run(
        db,
        auth,
        workflow_type="competitor_analysis",
        prompt_version=COMPETITOR_ANALYSIS_PROMPT_VERSION,
        input_summary=f"Generate competitor landscape for {project.name}"[:500],
        project_id=project.id,
        model_provider="stub" if settings.should_use_llm_stub else "litellm",
        model_name=settings.litellm_model,
    )
    try:
        project_state = _load_project_state_step(db, run, project)
        competitors = _load_seeded_competitors_step(db, auth, run, project, payload)
        ingested_source_count = _ingest_competitor_sources_step(
            db,
            auth,
            settings,
            run,
            competitors,
            payload.ingest_urls,
        )
        retrieval_results = _retrieve_competitor_evidence_step(
            db,
            auth,
            settings,
            run,
            project,
            project_state,
            competitors,
        )
        draft, completion, _generate_step = _generate_analysis_step(
            db,
            settings,
            run,
            project_state,
            competitors,
            retrieval_results,
        )
        audited_draft = _citation_audit_step(db, run, draft, retrieval_results)
        write_result = _write_analysis_step(db, auth, run, project, audited_draft)
    except (StructuredOutputError, RuntimeError, HTTPException) as exc:
        ai_run_service.fail_run(db, run, error=str(exc))
        raise
    except Exception as exc:
        ai_run_service.fail_run(db, run, error=str(exc))
        raise CompetitorAnalysisError("Competitor analysis failed.") from exc

    run = ai_run_service.complete_run(
        db,
        run,
        output_summary=audited_draft.summary[:1000],
        total_tokens=completion.total_tokens,
        total_cost=completion.total_cost,
        model_provider=completion.model_provider,
        model_name=completion.model_name,
    )
    return CompetitorAnalysisResult(
        run=run,
        step=write_result["step"],
        artifact=write_result["artifact"],
        competitors=write_result["competitors"],
        claims=write_result["claims"],
        citations=audited_draft.citations,
        unsupported_claims=audited_draft.unsupported_claims,
        retrieval_result_count=len(retrieval_results),
        ingested_source_count=ingested_source_count,
        model_provider=completion.model_provider,
        model_name=completion.model_name,
        used_stub=completion.used_stub,
        total_tokens=completion.total_tokens,
        total_cost=completion.total_cost,
    )


def _load_project_state_step(db: Session, run: AIRun, project: Project) -> dict[str, Any]:
    step = ai_run_service.start_step(
        db,
        run,
        step_name="load_project_state",
        input_json={"project_id": str(project.id)},
    )
    started = perf_counter()
    thesis = project_service.current_thesis(project)
    project_state = {
        "id": str(project.id),
        "name": project.name,
        "short_description": project.short_description,
        "current_thesis": thesis.thesis_text if thesis else None,
        "customer_segments": [segment.name for segment in project.customer_segments],
        "problem_hypotheses": [problem.description for problem in project.problems],
    }
    ai_run_service.complete_step(
        db,
        step,
        output_json=project_state,
        latency_ms=int((perf_counter() - started) * 1000),
        tokens=None,
        cost=Decimal("0"),
    )
    return project_state


def _load_seeded_competitors_step(
    db: Session,
    auth: AuthContext,
    run: AIRun,
    project: Project,
    payload: CompetitorAnalyzeCreate,
) -> list[Competitor]:
    step = ai_run_service.start_step(
        db,
        run,
        step_name="load_user_seeded_competitors",
        input_json=payload.model_dump(mode="json"),
    )
    started = perf_counter()
    for seed in payload.seed_competitors:
        _upsert_seed_competitor(db, auth, project.id, seed)
    db.commit()
    competitors = list_competitors(db, auth, project.id)
    ai_run_service.complete_step(
        db,
        step,
        output_json={
            "competitor_count": len(competitors),
            "competitors": [_competitor_bundle(competitor) for competitor in competitors],
        },
        latency_ms=int((perf_counter() - started) * 1000),
        tokens=None,
        cost=Decimal("0"),
    )
    return competitors


def _ingest_competitor_sources_step(
    db: Session,
    auth: AuthContext,
    settings: Settings,
    run: AIRun,
    competitors: list[Competitor],
    ingest_urls: bool,
) -> int:
    step = ai_run_service.start_step(
        db,
        run,
        step_name="fetch_competitor_sources",
        input_json={
            "ingest_urls": ingest_urls,
            "competitor_urls": [
                {"id": str(competitor.id), "name": competitor.name, "url": competitor.url}
                for competitor in competitors
                if competitor.url
            ],
        },
    )
    started = perf_counter()
    ingested_count = 0
    failures: list[dict[str, str]] = []
    if ingest_urls:
        for competitor in competitors:
            if not competitor.url:
                continue
            try:
                source = _ensure_competitor_source(db, auth, settings, competitor)
                if source is not None:
                    ingested_count += 1
            except Exception as exc:
                failures.append({"competitor": competitor.name, "error": str(exc)[:500]})

    ai_run_service.complete_step(
        db,
        step,
        output_json={"ingested_source_count": ingested_count, "failures": failures},
        latency_ms=int((perf_counter() - started) * 1000),
        tokens=None,
        cost=Decimal("0"),
    )
    return ingested_count


def _retrieve_competitor_evidence_step(
    db: Session,
    auth: AuthContext,
    settings: Settings,
    run: AIRun,
    project: Project,
    project_state: dict[str, Any],
    competitors: list[Competitor],
):
    query = _competitor_retrieval_query(project_state, competitors)
    payload = EvidenceRetrieveCreate(query=query, mode="hybrid", top_k=COMPETITOR_RETRIEVAL_TOP_K)
    step = ai_run_service.start_step(
        db,
        run,
        step_name="retrieve_competitor_evidence",
        input_json=payload.model_dump(mode="json"),
    )
    started = perf_counter()
    results = retrieval_service.retrieve_evidence_results(
        db,
        auth,
        settings,
        project.id,
        payload,
    )
    ai_run_service.complete_step(
        db,
        step,
        output_json={
            "query": query,
            "result_count": len(results),
            "results": [result.model_dump(mode="json") for result in results],
        },
        latency_ms=int((perf_counter() - started) * 1000),
        tokens=None,
        cost=Decimal("0"),
    )
    return results


def _generate_analysis_step(
    db: Session,
    settings: Settings,
    run: AIRun,
    project_state: dict[str, Any],
    competitors: list[Competitor],
    retrieval_results,
):
    messages = _competitor_messages(
        project_state,
        [_competitor_bundle(competitor) for competitor in competitors],
        _evidence_bundles(retrieval_results),
    )
    step = ai_run_service.start_step(
        db,
        run,
        step_name="extract_competitor_profiles",
        input_json={
            "schema": CompetitorAnalysisDraft.__name__,
            "messages": [message.model_dump() for message in messages],
        },
    )
    started = perf_counter()
    try:
        if should_use_fallback_without_model(settings):
            draft = _fallback_competitor_analysis(project_state, competitors, retrieval_results)
            completion = _fallback_completion(
                settings,
                messages,
                draft,
                "competitor_analysis_policy_always",
            )
        else:
            try:
                result = generate_structured_output(
                    settings,
                    CompetitorAnalysisDraft,
                    messages,
                    model=settings.litellm_model,
                    temperature=0.0,
                    max_tokens=COMPETITOR_MAX_TOKENS,
                )
                draft = CompetitorAnalysisDraft.model_validate(result.parsed)
                completion = result.completion
            except (StructuredOutputError, RuntimeError) as exc:
                if not should_use_fallback_after_error(settings):
                    raise
                draft = _fallback_competitor_analysis(project_state, competitors, retrieval_results)
                completion = _fallback_completion(
                    settings,
                    messages,
                    draft,
                    "competitor_analysis_emergency",
                    exc,
                )
    except Exception as exc:
        ai_run_service.fail_step(
            db,
            step,
            error=str(exc),
            latency_ms=int((perf_counter() - started) * 1000),
        )
        raise
    completed_step = ai_run_service.complete_step(
        db,
        step,
        output_json=draft.model_dump(mode="json"),
        latency_ms=int((perf_counter() - started) * 1000),
        tokens=completion.total_tokens,
        cost=completion.total_cost,
    )
    return draft, completion, completed_step


def _citation_audit_step(
    db: Session,
    run: AIRun,
    draft: CompetitorAnalysisDraft,
    retrieval_results,
) -> CompetitorAnalysisDraft:
    step = ai_run_service.start_step(
        db,
        run,
        step_name="citation_audit",
        input_json={
            "claim_count": len(draft.claims),
            "competitor_count": len(draft.competitors),
            "retrieved_chunk_ids": [str(result.chunk_id) for result in retrieval_results],
        },
    )
    started = perf_counter()
    audited = _audit_citations(draft, retrieval_results)
    ai_run_service.complete_step(
        db,
        step,
        output_json={
            "claim_count": len(audited.claims),
            "citation_count": len(audited.citations),
            "unsupported_claim_count": len(audited.unsupported_claims),
        },
        latency_ms=int((perf_counter() - started) * 1000),
        tokens=None,
        cost=Decimal("0"),
    )
    return audited


def _write_analysis_step(
    db: Session,
    auth: AuthContext,
    run: AIRun,
    project: Project,
    draft: CompetitorAnalysisDraft,
) -> dict[str, Any]:
    step = ai_run_service.start_step(
        db,
        run,
        step_name="write_competitor_landscape",
        input_json={
            "project_id": str(project.id),
            "competitor_count": len(draft.competitors),
            "claim_count": len(draft.claims),
        },
    )
    started = perf_counter()

    competitors = _upsert_competitor_profiles(db, auth, project, draft.competitors)
    artifact = _get_or_create_competitor_artifact(db, auth, project)
    version_number = _next_artifact_version(db, artifact.id)
    version = ArtifactVersion(
        workspace_id=auth.workspace_id,
        artifact_id=artifact.id,
        version=version_number,
        markdown_content=_render_markdown_landscape(project, draft),
        structured_content=draft.model_dump(mode="json"),
        generated_by_ai_run_id=run.id,
        created_by=auth.user_id,
    )
    db.add(version)
    db.flush()
    artifact.current_version_id = version.id
    claims = _write_claims(db, auth, project, version, draft.claims)

    db.commit()
    artifact = _load_artifact(db, auth, project.id, artifact.id)
    competitors = list_competitors(db, auth, project.id)
    claims = _load_claims_for_version(db, version.id)
    completed_step = ai_run_service.complete_step(
        db,
        step,
        output_json={
            "artifact_id": str(artifact.id),
            "artifact_version_id": str(version.id),
            "version": version.version,
            "competitor_ids": [str(competitor.id) for competitor in competitors],
            "claim_ids": [str(claim.id) for claim in claims],
        },
        latency_ms=int((perf_counter() - started) * 1000),
        tokens=None,
        cost=Decimal("0"),
    )
    return {
        "step": completed_step,
        "artifact": artifact,
        "competitors": competitors,
        "claims": claims,
    }


def _ensure_competitor_source(
    db: Session,
    auth: AuthContext,
    settings: Settings,
    competitor: Competitor,
) -> EvidenceSource | None:
    if not competitor.url:
        return None

    source = db.scalar(
        select(EvidenceSource)
        .where(
            EvidenceSource.workspace_id == auth.workspace_id,
            EvidenceSource.project_id == competitor.project_id,
            EvidenceSource.url == competitor.url,
        )
        .options(selectinload(EvidenceSource.chunks))
    )
    if source is None:
        payload = EvidenceUrlCreate(url=competitor.url, title=f"{competitor.name} website")
        source = evidence_service.add_url_source(db, auth, settings, competitor.project_id, payload)

    _link_competitor_source(db, competitor, source)
    db.commit()
    return source


def _link_competitor_source(
    db: Session,
    competitor: Competitor,
    source: EvidenceSource,
) -> None:
    if not source.chunks:
        _add_competitor_evidence_link(db, competitor, source.id, None)
        return

    for chunk in source.chunks:
        metadata = dict(chunk.chunk_metadata or {})
        metadata["competitor_id"] = str(competitor.id)
        metadata["competitor_name"] = competitor.name
        chunk.chunk_metadata = metadata
        _add_competitor_evidence_link(db, competitor, source.id, chunk.id)


def _add_competitor_evidence_link(
    db: Session,
    competitor: Competitor,
    source_id: uuid.UUID,
    chunk_id: uuid.UUID | None,
) -> None:
    existing = db.scalar(
        select(CompetitorEvidenceLink).where(
            CompetitorEvidenceLink.competitor_id == competitor.id,
            CompetitorEvidenceLink.evidence_source_id == source_id,
            CompetitorEvidenceLink.evidence_chunk_id == chunk_id,
        )
    )
    if existing is None:
        db.add(
            CompetitorEvidenceLink(
                competitor_id=competitor.id,
                evidence_source_id=source_id,
                evidence_chunk_id=chunk_id,
            )
        )


def _upsert_competitor_profiles(
    db: Session,
    auth: AuthContext,
    project: Project,
    drafts: list[CompetitorProfileDraft],
) -> list[Competitor]:
    competitors: list[Competitor] = []
    for draft in drafts:
        competitor = _find_existing_competitor(db, auth, project.id, draft.name, draft.url)
        if competitor is None:
            competitor = Competitor(
                workspace_id=auth.workspace_id,
                project_id=project.id,
                name=draft.name.strip(),
                url=draft.url,
            )
            db.add(competitor)
            db.flush()

        competitor.name = draft.name.strip()
        competitor.url = draft.url or competitor.url
        competitor.category = draft.category
        competitor.target_user = draft.target_user
        competitor.positioning = draft.positioning
        competitor.pricing_summary = draft.pricing_summary
        competitor.key_features = draft.key_features
        competitor.strengths = _bullets_to_text(draft.strengths)
        competitor.weaknesses = _bullets_to_text(draft.weaknesses)
        competitor.differentiation_notes = draft.differentiation_notes
        competitor.threat_level = draft.threat_level
        competitor.last_analyzed_at = datetime.now(UTC)
        for citation in draft.citations:
            _link_competitor_citation(db, competitor, citation)
        competitors.append(competitor)
    return competitors


def _link_competitor_citation(
    db: Session,
    competitor: Competitor,
    citation: Citation,
) -> None:
    _add_competitor_evidence_link(db, competitor, citation.source_id, citation.chunk_id)
    if citation.chunk_id is None:
        return
    chunk = db.scalar(select(EvidenceChunk).where(EvidenceChunk.id == citation.chunk_id))
    if chunk is not None:
        metadata = dict(chunk.chunk_metadata or {})
        metadata["competitor_id"] = str(competitor.id)
        metadata["competitor_name"] = competitor.name
        chunk.chunk_metadata = metadata


def _upsert_seed_competitor(
    db: Session,
    auth: AuthContext,
    project_id: uuid.UUID,
    payload: CompetitorCreate,
) -> Competitor:
    competitor = _find_existing_competitor(
        db,
        auth,
        project_id,
        payload.name,
        _url_text(payload.url),
    )
    if competitor is None:
        competitor = Competitor(
            workspace_id=auth.workspace_id,
            project_id=project_id,
            name=payload.name.strip(),
            url=_url_text(payload.url),
            category=payload.category,
            threat_level="unknown",
        )
        db.add(competitor)
        return competitor

    competitor.name = payload.name.strip()
    competitor.url = _url_text(payload.url) or competitor.url
    competitor.category = payload.category
    return competitor


def _find_existing_competitor(
    db: Session,
    auth: AuthContext,
    project_id: uuid.UUID,
    name: str,
    url: str | None,
) -> Competitor | None:
    if url:
        competitor = db.scalar(
            select(Competitor).where(
                Competitor.workspace_id == auth.workspace_id,
                Competitor.project_id == project_id,
                Competitor.url == url,
            )
        )
        if competitor is not None:
            return competitor

    normalized_name = _normalize_key(name)
    for competitor in db.scalars(
        select(Competitor).where(
            Competitor.workspace_id == auth.workspace_id,
            Competitor.project_id == project_id,
        )
    ):
        if _normalize_key(competitor.name) == normalized_name:
            return competitor
    return None


def _competitor_messages(
    project_state: dict[str, Any],
    seed_competitors: list[dict[str, Any]],
    evidence_bundles: list[dict[str, Any]],
) -> list[ChatMessage]:
    payload = {
        "project_state": project_state,
        "seed_competitors": seed_competitors,
        "required_output": [
            "competitor profiles",
            "direct/adjacent/substitute categorization",
            "positioning clusters",
            "underserved positioning gaps",
            "wedge recommendations",
            "where not to compete",
            "citations and unsupported claims",
        ],
    }
    evidence_payload = {"evidence_bundles": evidence_bundles}
    payload_json = json.dumps(payload, indent=2, sort_keys=True)
    evidence_json = json.dumps(evidence_payload, indent=2, sort_keys=True)
    return [
        ChatMessage(
            role="system",
            content=(
                "Generate a bounded competitor landscape for a founder. Use retrieved "
                "project and competitor evidence for factual claims. "
                f"{UNTRUSTED_RETRIEVED_CONTENT_RULE} "
                "Cite source_id/chunk_id values for specific factual claims and mark "
                "unsupported conclusions as inference."
            ),
        ),
        ChatMessage(
            role="user",
            content=(
                "Return structured JSON only with the schema fields at the top level; "
                "do not wrap the response in another object. Keep the local-dev response "
                "concise: one profile per seeded competitor, one cluster, up to 3 gaps, "
                "up to 3 wedge recommendations, up to 2 claims, and unsupported claims.\n\n"
                f"{payload_json}"
                "\n\n<untrusted_retrieved_content>\n"
                f"{evidence_json}"
                "\n</untrusted_retrieved_content>"
            ),
        ),
    ]


def _competitor_retrieval_query(
    project_state: dict[str, Any],
    competitors: list[Competitor],
) -> str:
    parts = [
        project_state.get("name"),
        project_state.get("short_description"),
        project_state.get("current_thesis"),
        " ".join(project_state.get("customer_segments") or []),
        " ".join(competitor.name for competitor in competitors),
        " ".join(competitor.url or "" for competitor in competitors),
        (
            "competitor pricing positioning features target users strengths weaknesses "
            "alternatives differentiation threat landscape"
        ),
    ]
    return " ".join(str(part) for part in parts if part)


def _evidence_bundles(retrieval_results) -> list[dict[str, Any]]:
    retrieved_at = datetime.now(UTC).isoformat()
    return [
        {
            "source_id": str(result.source_id),
            "chunk_id": str(result.chunk_id),
            "title": result.title,
            "url": result.url,
            "source_type": result.source_type,
            "chunk_index": result.chunk_index,
            "text": result.text[:COMPETITOR_EVIDENCE_TEXT_LIMIT],
            "score": result.score,
            "metadata": result.metadata,
            "retrieved_at": retrieved_at,
        }
        for result in retrieval_results
    ]


def _fallback_competitor_analysis(
    project_state: dict[str, Any],
    competitors: list[Competitor],
    retrieval_results,
) -> CompetitorAnalysisDraft:
    project_name = str(project_state.get("name") or "This project")
    profiles = [
        _fallback_profile(competitor, _competitor_citations(competitor, retrieval_results))
        for competitor in competitors
    ]
    citations = _dedupe_citations(
        [citation for profile in profiles for citation in profile.citations]
    )
    claims = [
        ClaimDraft(
            text=(
                "The competitor landscape is based on user-seeded competitors and retrieved "
                "project evidence."
            ),
            claim_type="competitor_evidence",
            confidence_score=0.7 if citations else 0.4,
            support_level="supported" if citations else "inference",
            citations=citations[:1],
        )
    ]
    if profiles:
        claims.append(
            ClaimDraft(
                text=(
                    f"{profiles[0].name} should be treated as a comparison point, but pricing "
                    "and feature depth still require source verification."
                ),
                claim_type="competitor_positioning",
                confidence_score=0.5,
                support_level="inference",
                citations=[],
            )
        )
    return CompetitorAnalysisDraft(
        summary=(
            f"{project_name} has an initial competitor landscape, but the evidence is still thin; "
            "treat this as a working map for follow-up research."
        ),
        competitors=profiles,
        clusters=[
            CompetitorClusterDraft(
                name="Seeded alternatives",
                competitors=[profile.name for profile in profiles],
                positioning_summary=(
                    "Current alternatives should be compared on workflow depth, source "
                    "traceability, and whether they support the user's learning journey."
                ),
            )
        ],
        positioning_gaps=[
            "Beginner-friendly plant care education tied to specific user questions",
            "Visible evidence and unsupported claims in learning recommendations",
            "Community or event workflows that go beyond static plant lookup",
        ],
        wedge_recommendations=[
            "Start with one narrow plant-care learning workflow and make source quality visible.",
            "Use competitor research to verify pricing, feature coverage, and user segment focus.",
        ],
        where_not_to_compete=[
            "Generic plant facts without context",
            "Unverified market-size or pricing claims",
            "Broad autonomous crawling before source quality is dependable",
        ],
        claims=claims,
        citations=citations,
        unsupported_claims=[
            (
                "Competitor pricing, feature completeness, and threat level need direct "
                "source verification."
            )
        ],
    )


def _fallback_profile(
    competitor: Competitor,
    citations: list[Citation],
) -> CompetitorProfileDraft:
    evidence_text = " ".join(
        item for citation in citations for item in [citation.title, citation.quote] if item
    ).casefold()
    key_features = competitor.key_features or []
    if not key_features:
        key_features = ["Public web presence"]
        if "identification" in evidence_text:
            key_features.insert(0, "Plant identification")

    return CompetitorProfileDraft(
        name=competitor.name,
        url=competitor.url,
        category=competitor.category,
        target_user=competitor.target_user
        or "People looking for plant information or adjacent plant-care workflows.",
        positioning=competitor.positioning
        or (
            f"{competitor.name} is a user-seeded alternative that should be compared against "
            "the project's plant-care learning workflow."
        ),
        pricing_summary=competitor.pricing_summary
        or "Pricing should be verified from current source material.",
        key_features=key_features,
        strengths=_text_to_bullets(
            competitor.strengths,
            [
                "Already discoverable as an alternative",
                "Provides a concrete reference point for user expectations",
            ],
        ),
        weaknesses=_text_to_bullets(
            competitor.weaknesses,
            [
                "Depth of plant-care education is unverified",
                "Community or event support is unverified",
            ],
        ),
        differentiation_notes=competitor.differentiation_notes
        or (
            "Differentiate by connecting plant-care guidance to a learning path, visible "
            "sources, and social practice instead of only lookup."
        ),
        threat_level=competitor.threat_level,
        citations=citations,
    )


def _competitor_citations(competitor: Competitor, retrieval_results) -> list[Citation]:
    citations: list[Citation] = []
    seen: set[tuple[str | None, str | None, str]] = set()
    for result in retrieval_results:
        metadata = result.metadata or {}
        if metadata.get("competitor_id") != str(competitor.id) and metadata.get(
            "competitor_name"
        ) != competitor.name:
            continue
        quote = result.text[:260]
        key = (result.url, result.title, quote)
        if key in seen:
            continue
        seen.add(key)
        citations.append(
            Citation(
                source_id=result.source_id,
                chunk_id=result.chunk_id,
                title=result.title,
                url=result.url,
                quote=quote,
                relevance_score=result.score,
            )
        )
    return citations[:3]


def _text_to_bullets(value: str | None, fallback: list[str]) -> list[str]:
    if value is None:
        return fallback
    bullets = [
        line.removeprefix("-").removeprefix("*").strip()
        for line in value.splitlines()
        if line.strip()
    ]
    return bullets or fallback


def _fallback_completion(
    settings: Settings,
    messages: list[ChatMessage],
    draft: CompetitorAnalysisDraft,
    fallback_name: str,
    error: BaseException | None = None,
) -> LLMCompletion:
    content = draft.model_dump_json()
    prompt_tokens = sum(len(message.content.split()) for message in messages)
    completion_tokens = len(content.split())
    return LLMCompletion(
        content=content,
        model_provider="local-fallback",
        model_name=settings.litellm_model,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        total_tokens=prompt_tokens + completion_tokens,
        total_cost=Decimal("0"),
        raw_response={
            "fallback": fallback_name,
            "error": str(error)[:500] if error is not None else None,
        },
        used_stub=True,
    )


def _audit_citations(
    draft: CompetitorAnalysisDraft,
    retrieval_results,
) -> CompetitorAnalysisDraft:
    valid_by_chunk = {result.chunk_id: result for result in retrieval_results}
    valid_by_source = {result.source_id: result for result in retrieval_results}
    unsupported_claims = list(dict.fromkeys(draft.unsupported_claims))
    audited_claims: list[ClaimDraft] = []
    global_citations: list[Citation] = []

    audited_profiles: list[CompetitorProfileDraft] = []
    for profile in draft.competitors:
        valid_profile_citations = [
            citation
            for citation in profile.citations
            if _citation_is_valid(citation, valid_by_chunk, valid_by_source)
        ]
        audited_profiles.append(profile.model_copy(update={"citations": valid_profile_citations}))
        global_citations.extend(valid_profile_citations)

    for claim in draft.claims:
        valid_citations = [
            citation
            for citation in claim.citations
            if _citation_is_valid(citation, valid_by_chunk, valid_by_source)
        ]
        if claim.support_level == "supported" and not valid_citations:
            unsupported_claims.append(claim.text)
            audited_claims.append(
                claim.model_copy(update={"support_level": "unsupported", "citations": []})
            )
            continue
        audited_claims.append(claim.model_copy(update={"citations": valid_citations}))
        global_citations.extend(valid_citations)

    for citation in draft.citations:
        if _citation_is_valid(citation, valid_by_chunk, valid_by_source):
            global_citations.append(citation)

    return draft.model_copy(
        update={
            "competitors": audited_profiles,
            "claims": audited_claims,
            "citations": _dedupe_citations(global_citations),
            "unsupported_claims": list(dict.fromkeys(unsupported_claims)),
        }
    )


def _citation_is_valid(
    citation: Citation,
    valid_by_chunk: dict[uuid.UUID, Any],
    valid_by_source: dict[uuid.UUID, Any],
) -> bool:
    if citation.chunk_id is not None:
        return citation.chunk_id in valid_by_chunk
    return citation.source_id in valid_by_source


def _dedupe_citations(citations: list[Citation]) -> list[Citation]:
    seen: set[tuple[str, str | None]] = set()
    deduped: list[Citation] = []
    for citation in citations:
        key = (str(citation.source_id), str(citation.chunk_id) if citation.chunk_id else None)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(citation)
    return deduped


def _get_or_create_competitor_artifact(
    db: Session,
    auth: AuthContext,
    project: Project,
) -> Artifact:
    artifact = db.scalar(
        select(Artifact).where(
            Artifact.workspace_id == auth.workspace_id,
            Artifact.project_id == project.id,
            Artifact.artifact_type == "competitor_landscape",
        )
    )
    if artifact is not None:
        return artifact
    artifact = Artifact(
        workspace_id=auth.workspace_id,
        project_id=project.id,
        artifact_type="competitor_landscape",
        title=f"{project.name} Competitor Landscape",
        created_by=auth.user_id,
    )
    db.add(artifact)
    db.flush()
    return artifact


def _load_artifact(
    db: Session,
    auth: AuthContext,
    project_id: uuid.UUID,
    artifact_id: uuid.UUID,
) -> Artifact:
    artifact = db.scalar(
        select(Artifact)
        .where(
            Artifact.id == artifact_id,
            Artifact.workspace_id == auth.workspace_id,
            Artifact.project_id == project_id,
        )
        .options(
            selectinload(Artifact.versions)
            .selectinload(ArtifactVersion.claims)
            .selectinload(Claim.evidence_links)
        )
    )
    if artifact is None:
        raise CompetitorAnalysisError("Generated artifact was not found.")
    return artifact


def _next_artifact_version(db: Session, artifact_id: uuid.UUID) -> int:
    current_max = db.scalar(
        select(func.max(ArtifactVersion.version)).where(ArtifactVersion.artifact_id == artifact_id)
    )
    return int(current_max or 0) + 1


def _write_claims(
    db: Session,
    auth: AuthContext,
    project: Project,
    version: ArtifactVersion,
    drafts: list[ClaimDraft],
) -> list[Claim]:
    claims: list[Claim] = []
    for draft in drafts:
        claim = Claim(
            workspace_id=auth.workspace_id,
            project_id=project.id,
            artifact_version_id=version.id,
            text=draft.text.strip(),
            claim_type=_optional_truncate(draft.claim_type, 80),
            confidence_score=_decimal_score(draft.confidence_score),
            support_level=draft.support_level,
        )
        db.add(claim)
        db.flush()
        for citation in draft.citations:
            db.add(
                ClaimEvidenceLink(
                    claim_id=claim.id,
                    evidence_source_id=citation.source_id,
                    evidence_chunk_id=citation.chunk_id,
                    relevance_score=_decimal_score(citation.relevance_score),
                    quote=citation.quote,
                )
            )
        claims.append(claim)
    return claims


def _load_claims_for_version(db: Session, version_id: uuid.UUID) -> list[Claim]:
    return list(
        db.scalars(
            select(Claim)
            .where(Claim.artifact_version_id == version_id)
            .options(selectinload(Claim.evidence_links))
            .order_by(Claim.created_at)
        )
    )


def _render_markdown_landscape(project: Project, draft: CompetitorAnalysisDraft) -> str:
    profiles = "\n\n".join(_render_profile(profile) for profile in draft.competitors)
    clusters = "\n".join(
        f"- {cluster.name}: {cluster.positioning_summary}" for cluster in draft.clusters
    ) or "- No clusters generated."
    gaps = "\n".join(f"- {gap}" for gap in draft.positioning_gaps) or "- None"
    wedges = "\n".join(f"- {item}" for item in draft.wedge_recommendations) or "- None"
    avoid = "\n".join(f"- {item}" for item in draft.where_not_to_compete) or "- None"
    citations = "\n".join(
        f"- {citation.title or citation.source_id}: {citation.quote or 'No quote captured.'}"
        for citation in draft.citations
    ) or "- No cited evidence available."
    unsupported = "\n".join(f"- {claim}" for claim in draft.unsupported_claims) or "- None"
    return "\n\n".join(
        [
            f"# Competitor Landscape: {project.name}",
            f"## Summary\n{draft.summary}",
            f"## Competitor Profiles\n{profiles or 'No competitor profiles generated.'}",
            f"## Positioning Clusters\n{clusters}",
            f"## Positioning Gaps\n{gaps}",
            f"## Wedge Recommendations\n{wedges}",
            f"## Where Not To Compete\n{avoid}",
            f"## Evidence Appendix\n{citations}",
            f"## Unsupported Claims / Open Questions\n{unsupported}",
        ]
    )


def _render_profile(profile: CompetitorProfileDraft) -> str:
    features = ", ".join(profile.key_features) or "Unknown"
    strengths = "; ".join(profile.strengths) or "Unknown"
    weaknesses = "; ".join(profile.weaknesses) or "Unknown"
    lines = [
        f"### {profile.name}",
        f"- Category: {profile.category}",
        f"- Threat level: {profile.threat_level}",
        f"- URL: {profile.url or 'Unknown'}",
        f"- Target user: {profile.target_user or 'Unknown'}",
        f"- Positioning: {profile.positioning or 'Unknown'}",
        f"- Pricing: {profile.pricing_summary or 'Unknown'}",
        f"- Key features: {features}",
        f"- Strengths: {strengths}",
        f"- Weaknesses: {weaknesses}",
        f"- Differentiation notes: {profile.differentiation_notes or 'Unknown'}",
    ]
    return "\n".join(lines)


def _competitor_bundle(competitor: Competitor) -> dict[str, Any]:
    return {
        "id": str(competitor.id),
        "name": competitor.name,
        "url": competitor.url,
        "category": competitor.category,
        "target_user": competitor.target_user,
        "positioning": competitor.positioning,
        "pricing_summary": competitor.pricing_summary,
        "key_features": competitor.key_features,
        "threat_level": competitor.threat_level,
    }


def _bullets_to_text(items: list[str]) -> str | None:
    cleaned = [item.strip() for item in items if item.strip()]
    return "\n".join(f"- {item}" for item in cleaned) if cleaned else None


def _decimal_score(value: float | None) -> Decimal | None:
    return Decimal(str(round(value, 4))) if value is not None else None


def _optional_truncate(value: str | None, max_length: int) -> str | None:
    if value is None:
        return None
    stripped = value.strip()
    return stripped[:max_length] if stripped else None


def _url_text(value: Any) -> str | None:
    return str(value).strip() if value is not None and str(value).strip() else None


def _normalize_key(value: str) -> str:
    return " ".join(value.casefold().split())
