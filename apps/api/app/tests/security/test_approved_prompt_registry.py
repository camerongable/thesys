import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.models import AIRun
from app.security import prompt_registry
from app.services import ai_run_service
from app.services.identity_service import ensure_dev_identity


def test_approved_prompt_registry_covers_all_active_prompt_content() -> None:
    active_contents = prompt_registry.active_prompt_contents()
    approved_versions = {
        f"thesys:{approval.prompt_name}:{approval.version}"
        for approval in prompt_registry.APPROVED_PROMPT_VERSIONS
    }

    assert set(active_contents) == approved_versions
    for prompt_version, content in active_contents.items():
        prompt_registry.ensure_approved_prompt_version(prompt_version)
        assert len(content) > 0


def test_unapproved_prompt_version_is_rejected_before_ai_run_persistence(
    db_session: Session,
) -> None:
    auth = ensure_dev_identity(
        db_session,
        email="prompt-registry@thesys.local",
        display_name="Prompt Registry",
        role="owner",
    )

    with pytest.raises(
        prompt_registry.ApprovedPromptRegistryError,
        match="not approved",
    ):
        ai_run_service.start_run(
            db_session,
            auth,
            workflow_type="prompt_registry_test",
            prompt_version="thesys:unreviewed-workflow:v1",
            input_summary="Verify prompt approval happens before persistence.",
        )

    assert db_session.scalar(select(func.count()).select_from(AIRun)) == 0


def test_modified_prompt_content_fails_approval_validation(monkeypatch) -> None:
    prompt_version = "thesys:guide-chat:v2"
    contents = prompt_registry.active_prompt_contents()
    contents[prompt_version] = "modified without a reviewed version"
    monkeypatch.setattr(prompt_registry, "active_prompt_contents", lambda: contents)

    with pytest.raises(
        prompt_registry.ApprovedPromptRegistryError,
        match="does not match",
    ):
        prompt_registry.ensure_approved_prompt_version(prompt_version)
