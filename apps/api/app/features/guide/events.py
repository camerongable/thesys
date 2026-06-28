"""Streaming event serialization helpers for Ask Thesys."""

from collections.abc import Iterator
from typing import Any

from app.schemas.guide import GuideChatResponseRead


def retrieval_started_events(message: str) -> Iterator[tuple[str, dict[str, Any]]]:
    payload = {"query": message[:500], "mode": "hybrid", "top_k": 5}
    yield ("retrieval_started", payload)
    yield (
        "tool_call_started",
        {
            "tool_name": "search_project_evidence",
            "access_mode": "read",
            "risk_level": "low",
            "input": payload,
        },
    )


def retrieval_completed_events(
    response: GuideChatResponseRead,
) -> Iterator[tuple[str, dict[str, Any]]]:
    diagnostics = response.retrieval_diagnostics or {}
    result_count = retrieval_result_count(response)
    yield (
        "tool_call_completed",
        {
            "tool_name": "search_project_evidence",
            "status": "succeeded",
            "result_count": result_count,
            "cited_evidence_ids": response.cited_evidence_ids,
        },
    )
    yield (
        "retrieval_result",
        {
            "result_count": result_count,
            "cited_evidence_ids": response.cited_evidence_ids,
            "citation_details": [
                detail.model_dump(mode="json") for detail in response.citation_details
            ],
            "diagnostics": diagnostics,
        },
    )
    if response.context_pack:
        yield (
            "context_compiled",
            {
                "context_pack_id": response.context_pack.get("id"),
                "workflow_type": response.context_pack.get("workflow_type"),
                "item_count": len(response.context_pack.get("items") or []),
                "dropped_count": len(response.context_pack.get("dropped_items") or []),
                "available_citation_ids": response.context_pack.get("available_citation_ids")
                or [],
                "selected_memory_ids": (
                    response.context_pack.get("metadata", {}).get("selected_memory_ids", [])
                    if isinstance(response.context_pack.get("metadata"), dict)
                    else []
                ),
            },
        )


def retrieval_result_count(response: GuideChatResponseRead) -> int:
    diagnostics = response.retrieval_diagnostics or {}
    context_diagnostics = diagnostics.get("context") if isinstance(diagnostics, dict) else None
    if isinstance(context_diagnostics, dict):
        selected_count = context_diagnostics.get("selected_count")
        if isinstance(selected_count, int):
            return selected_count
    return len(response.cited_evidence_ids)


def answer_delta_chunks(answer: str, *, max_chars: int = 96) -> list[str]:
    words = answer.split()
    if not words:
        return [answer]
    chunks: list[str] = []
    current = ""
    for word in words:
        candidate = f"{current} {word}".strip()
        if current and len(candidate) > max_chars:
            chunks.append(current + " ")
            current = word
        else:
            current = candidate
    if current:
        chunks.append(current)
    return chunks


def final_stream_metadata(response: GuideChatResponseRead) -> dict[str, Any]:
    context_pack = response.context_pack or {}
    return {
        "ai_run_id": str(response.ai_run_id) if response.ai_run_id else None,
        "used_llm": response.used_llm,
        "confidence_level": response.confidence_level,
        "cited_evidence_ids": response.cited_evidence_ids,
        "citation_count": len(response.citation_details),
        "proposal_invocation_id": str(response.proposal_invocation_id)
        if response.proposal_invocation_id
        else None,
        "approval_request_id": str(response.approval_request_id)
        if response.approval_request_id
        else None,
        "context_pack_id": context_pack.get("id") if isinstance(context_pack, dict) else None,
    }


def partial_answer_from_json(raw_content: str) -> str:
    key_index = raw_content.find('"answer"')
    if key_index < 0:
        return ""
    colon_index = raw_content.find(":", key_index)
    if colon_index < 0:
        return ""
    quote_index = raw_content.find('"', colon_index)
    if quote_index < 0:
        return ""
    chars: list[str] = []
    escaped = False
    for character in raw_content[quote_index + 1 :]:
        if escaped:
            chars.append(json_escape_character(character))
            escaped = False
            continue
        if character == "\\":
            escaped = True
            continue
        if character == '"':
            break
        chars.append(character)
    return "".join(chars)


def json_escape_character(character: str) -> str:
    escapes = {
        '"': '"',
        "\\": "\\",
        "/": "/",
        "b": "\b",
        "f": "\f",
        "n": "\n",
        "r": "\r",
        "t": "\t",
    }
    return escapes.get(character, character)
