"""Reviewed prompt approvals for production Thesys workflows."""

import hashlib
from dataclasses import dataclass

from app.ai import prompts


@dataclass(frozen=True)
class ApprovedPromptVersion:
    prompt_name: str
    version: str
    content_hash: str
    security_eval_version: str
    approved_at: str
    approved_by: str
    enabled: bool


class ApprovedPromptRegistryError(ValueError):
    pass


_APPROVAL_METADATA = {
    "security_eval_version": "redteam-corpus:v1",
    "approved_at": "2026-07-18T00:00:00Z",
    "approved_by": "platform-security",
    "enabled": True,
}


APPROVED_PROMPT_VERSIONS = (
    ApprovedPromptVersion(
        prompt_name="agentic-research",
        version="v1",
        content_hash="143840e60fb6f153a3f9b3daf75fe6abc66da5b437fc57b5ba36e1ac5cf787b6",
        **_APPROVAL_METADATA,
    ),
    ApprovedPromptVersion(
        prompt_name="assumption-extraction",
        version="v1",
        content_hash="66bbf009f7491baff2ff6fd42095f2d28c1ab867b8a863e8c8a3cd5da7a4b53e",
        **_APPROVAL_METADATA,
    ),
    ApprovedPromptVersion(
        prompt_name="competitor-analysis",
        version="v1",
        content_hash="1fd2feb5ad3a931a66dc2f770d8309471aebc1b8034a27401ca8cab815d63202",
        **_APPROVAL_METADATA,
    ),
    ApprovedPromptVersion(
        prompt_name="competitor-discovery",
        version="v1",
        content_hash="c7d62bae95fd19a3a751619987851bea27e5f2defc3977293e344fd18bf8a4c1",
        **_APPROVAL_METADATA,
    ),
    ApprovedPromptVersion(
        prompt_name="conversational-investigation-intake",
        version="v1",
        content_hash="80716ef1c39cc26c835005f0651d507497ad7b891816238eeaed167d074b6758",
        **_APPROVAL_METADATA,
    ),
    ApprovedPromptVersion(
        prompt_name="evidence-ingestion",
        version="v1",
        content_hash="c17d75856dc035755eb30ba6f45da5b827ab31fb8bba3be14070364ecd55575e",
        **_APPROVAL_METADATA,
    ),
    ApprovedPromptVersion(
        prompt_name="evidence-retrieval",
        version="v1",
        content_hash="914ddf71b8f80d475f460d390fbb6a3970e7387893dd4c9da2f815d895e8d79e",
        **_APPROVAL_METADATA,
    ),
    ApprovedPromptVersion(
        prompt_name="guide-chat",
        version="v2",
        content_hash="a3c90e498453b38c48ab5823a3ac503f230ea7f1bc49bac9d84629988a9b87e1",
        **_APPROVAL_METADATA,
    ),
    ApprovedPromptVersion(
        prompt_name="opportunity-brief",
        version="v1",
        content_hash="1b36339a32c9151100655aae2ebd959f790260bf92dbf0828d574f24f4035228",
        **_APPROVAL_METADATA,
    ),
    ApprovedPromptVersion(
        prompt_name="research-sprint-planning",
        version="v1",
        content_hash="cf9b25485771d8b762a968c3173c56755c2c22cb43b027f152ec79a5791b8057",
        **_APPROVAL_METADATA,
    ),
    ApprovedPromptVersion(
        prompt_name="source-discovery",
        version="v1",
        content_hash="f17d4b0303ad002b03204ede4afc67883951ed23c26930a21835f9768a345f27",
        **_APPROVAL_METADATA,
    ),
    ApprovedPromptVersion(
        prompt_name="structured-intake-finalize",
        version="v1",
        content_hash="5a3133a9e1e6489792c1245cfa6f3a3c818c070a2c57a9888eeaf8f8cd99521c",
        **_APPROVAL_METADATA,
    ),
    ApprovedPromptVersion(
        prompt_name="structured-intake",
        version="v1",
        content_hash="20bfcf2cae0e4e8bb0e66bb5e378822be61dca28cc8b10dda072b8cf929aceb2",
        **_APPROVAL_METADATA,
    ),
    ApprovedPromptVersion(
        prompt_name="structured-output-smoke-test",
        version="v1",
        content_hash="030dee89ddb0f5d965f0cc0a268b90c85ab276251a5c08f37ed2f2c541602f71",
        **_APPROVAL_METADATA,
    ),
    ApprovedPromptVersion(
        prompt_name="untrusted-retrieved-content-rule",
        version="v1",
        content_hash="053d92d2979994d7d4406ec1b8de3b518d142adf896d9e886cb4874d6968a91d",
        **_APPROVAL_METADATA,
    ),
    ApprovedPromptVersion(
        prompt_name="validation-plan",
        version="v1",
        content_hash="9fcb258230005fe62204cdfea55b42f4772d52037bb5b4f52a07c3009d016fa6",
        **_APPROVAL_METADATA,
    ),
    ApprovedPromptVersion(
        prompt_name="validation-result-interpretation",
        version="v1",
        content_hash="0e6c7b27cd6281866d33e67f7d765decd32662b1f1bff11b4bfbb83acb9627b1",
        **_APPROVAL_METADATA,
    ),
)


def ensure_approved_prompt_version(prompt_version: str) -> None:
    """Fail closed for production workflow prompt versions before their execution starts."""
    if not prompt_version.startswith(f"{prompts.PROMPT_VERSION_NAMESPACE}:"):
        return
    prompt_name, version = _split_prompt_version(prompt_version)
    approval = _find_approval(prompt_name=prompt_name, version=version)
    content = active_prompt_contents().get(prompt_version)
    if approval is None or not approval.enabled or content is None:
        raise ApprovedPromptRegistryError("Prompt version is not approved for execution.")
    if approval.content_hash != _content_hash(content):
        raise ApprovedPromptRegistryError("Prompt content does not match its approved version.")


def active_prompt_contents() -> dict[str, str]:
    prompt_versions = {
        value
        for name, value in vars(prompts).items()
        if name.endswith("_PROMPT_VERSION") and isinstance(value, str)
    }
    contents = {prompt_version: prompt_version for prompt_version in prompt_versions}
    contents[f"{prompts.PROMPT_VERSION_NAMESPACE}:untrusted-retrieved-content-rule:v1"] = (
        prompts.UNTRUSTED_RETRIEVED_CONTENT_RULE
    )
    return contents


def _find_approval(*, prompt_name: str, version: str) -> ApprovedPromptVersion | None:
    return next(
        (
            approval
            for approval in APPROVED_PROMPT_VERSIONS
            if approval.prompt_name == prompt_name and approval.version == version
        ),
        None,
    )


def _split_prompt_version(prompt_version: str) -> tuple[str, str]:
    _, prompt_name, version = prompt_version.split(":", maxsplit=2)
    return prompt_name, version


def _content_hash(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()
