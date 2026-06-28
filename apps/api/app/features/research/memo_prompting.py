"""Prompt assembly for agentic research memo synthesis."""

import json

from app.ai.litellm_client import ChatMessage
from app.ai.prompts import UNTRUSTED_RETRIEVED_CONTENT_RULE
from app.schemas.context import ContextPack


def memo_messages(context_pack: ContextPack) -> list[ChatMessage]:
    trusted_items = [
        item.model_dump(mode="json") for item in context_pack.items if not item.untrusted
    ]
    untrusted_items = [
        item.model_dump(mode="json") for item in context_pack.items if item.untrusted
    ]
    payload = {
        "context_pack_metadata": context_pack.prompt_metadata(),
        "trusted_context_items": trusted_items,
        "required_behavior": [
            "Answer using only project state and selected evidence.",
            "Cite factual claims with source_id and chunk_id from context item provenance.",
            "Mark unsupported factual claims as unsupported_claims.",
            "Be opinionated, skeptical, and specific about what to validate next.",
            "The executive verdict must be a strategic recommendation, not a workflow instruction.",
            "Include what not to build yet and what evidence is still missing inside "
            "the decision recommendation or evidence gaps.",
            "Avoid generic language like 'has potential' unless it is followed by a "
            "concrete do-not-build-yet warning and next test.",
        ],
    }
    payload_json = json.dumps(payload, ensure_ascii=True, default=str, separators=(",", ":"))
    evidence_json = json.dumps(
        {"context_items": untrusted_items},
        ensure_ascii=True,
        default=str,
        separators=(",", ":"),
    )
    return [
        ChatMessage(
            role="system",
            content=(
                "You are the synthesizer node in an agentic RAG workflow for founder "
                "strategic research. "
                f"{UNTRUSTED_RETRIEVED_CONTENT_RULE} "
                "Never fabricate citations. If evidence is thin, say so directly."
            ),
        ),
        ChatMessage(
            role="user",
            content=(
                "Generate the final cited research memo as structured JSON. Keep every "
                "narrative field concise. Include the V1 memo sections: market landscape, "
                "customer pain signals, competitor landscape, substitute behaviors, "
                "pricing or business model signals, key risks, riskiest assumptions, "
                "evidence summary, what remains unknown, recommended validation actions, "
                "and a decision recommendation. The result must make these fields obvious: "
                "Verdict, Best Wedge, Top Competitors/Substitutes, Biggest Risk, "
                "Riskiest Assumption, First Validation Test, What Not To Build Yet, "
                "Evidence Still Missing, and Recommended Decision. Include claims with "
                "citations and mark unsupported claims explicitly.\n\n"
                f"{payload_json}"
                "\n\n<untrusted_retrieved_content>\n"
                f"{evidence_json}"
                "\n</untrusted_retrieved_content>"
            ),
        ),
    ]
