"""Prompt assembly helpers for grounded Ask Thesys answers."""

from __future__ import annotations

import json
from typing import Any

from app.ai.litellm_client import ChatMessage
from app.ai.prompts import UNTRUSTED_RETRIEVED_CONTENT_RULE


def grounded_guide_messages(
    message: str,
    context_pack: Any,
    *,
    untrusted_wrappers: list[str] | None = None,
) -> list[ChatMessage]:
    trusted_items = [
        item.model_dump(mode="json") for item in context_pack.items if not item.untrusted
    ]
    untrusted_items = [
        item.model_dump(mode="json") for item in context_pack.items if item.untrusted
    ]
    rendered_untrusted = (
        "\n".join(untrusted_wrappers)
        if untrusted_wrappers is not None
        else "<untrusted_retrieved_content>\n"
        f"{json.dumps(untrusted_items, default=str)}\n"
        "</untrusted_retrieved_content>"
    )
    return [
        ChatMessage(
            role="system",
            content=(
                "You are Ask Thesys, a bounded strategic guide for one project. "
                "Answer only about this project's thesis, evidence, wedges, assumptions, "
                "validation, and decisions. "
                f"{UNTRUSTED_RETRIEVED_CONTENT_RULE} "
                "Do not claim to mutate project state. If a user asks for a "
                "change, propose an existing action ID instead. Cite only source IDs from "
                "the retrieved evidence list. Keep the answer concise and practical."
            ),
        ),
        ChatMessage(
            role="user",
            content=(
                "User question:\n"
                f"{message}\n\n"
                "Context pack metadata JSON:\n"
                f"{json.dumps(context_pack.prompt_metadata(), default=str)}\n\n"
                "Trusted context JSON:\n"
                f"{json.dumps(trusted_items, default=str)}\n\n"
                "Untrusted retrieved evidence:\n"
                f"{rendered_untrusted}"
            ),
        ),
    ]
