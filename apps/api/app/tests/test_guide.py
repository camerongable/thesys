from fastapi.testclient import TestClient


def test_guide_context_and_recommendation_are_stage_aware(client: TestClient) -> None:
    project_id = client.post(
        "/api/projects",
        json={"name": "Guide test idea"},
    ).json()["id"]

    draft = _guide_context(client, project_id)
    assert draft["stage"] == "draft_idea"
    assert draft["next_action"] == "Define the thesis"
    assert draft["confidence_level"] == "unknown"
    assert draft["available_actions"][0]["id"] == "structure_idea"

    draft_recommend = _guide_recommend(client, project_id)
    assert draft_recommend["current_focus"] == "Shape the rough idea into a testable thesis."
    assert draft_recommend["recommended_action"]["target_route"].endswith("#structured-intake")
    assert draft_recommend["recommended_action"]["label"] == "Open thesis structure form"
    assert draft_recommend["after_that"]
    assert len(draft_recommend["secondary_actions"]) <= 3
    assert draft_recommend["suggested_questions"]

    extract_response = client.post(f"/api/projects/{project_id}/assumptions/extract")
    assert extract_response.status_code == 200
    assumptions = _guide_context(client, project_id)
    assert assumptions["stage"] == "assumptions_identified"
    assert assumptions["biggest_unknown"]
    assert assumptions["risk_level"] == "high"
    assert assumptions["available_actions"][0]["id"] == "create_validation_plan"

    plan_response = client.post(
        f"/api/projects/{project_id}/experiments/validation-plan",
        json={"assumption_ids": [extract_response.json()["assumptions"][0]["id"]], "max_plans": 1},
    )
    assert plan_response.status_code == 200
    validation = _guide_context(client, project_id)
    assert validation["stage"] == "validation_plan_created"
    assert validation["active_validation_plan_id"] is not None
    assert validation["available_actions"][0]["id"] == "log_results"
    assert validation["available_actions"][0]["label"] == "Open validation result form"
    assert any(
        action["id"] == "open_validation_mission"
        and action["target_route"].endswith("#validation-mission")
        for action in validation["available_actions"]
    )
    assert any(
        action["id"] == "interpret_validation_notes"
        and action["target_modal"] == "interpret-result"
        for action in validation["available_actions"]
    )

    experiment = plan_response.json()["experiments"][0]
    result_response = client.post(
        f"/api/projects/{project_id}/experiments/{experiment['id']}/results",
        json={
            "result_summary": "Three of five target users described urgent pain.",
            "outcome": "mixed",
            "raw_notes": "Useful pain signal, weak willingness-to-pay signal.",
        },
    )
    assert result_response.status_code == 200
    decision_ready = _guide_context(client, project_id)
    assert decision_ready["stage"] == "decision_ready"
    assert decision_ready["available_actions"][0]["id"] == "use_suggested_decision"

    seed_response = client.post("/api/demo/seed")
    assert seed_response.status_code == 200
    demo_id = seed_response.json()["project"]["id"]
    demo_context = _guide_context(client, demo_id)
    assert demo_context["stage"] == "decision_ready"
    decision_ready_demo = _guide_recommend(client, demo_id)
    assert decision_ready_demo["recommended_action"]["id"] == "use_suggested_decision"
    assert "decision" in decision_ready_demo["current_focus"].lower()


def test_guide_action_execution_routes_known_actions(client: TestClient) -> None:
    project_id = client.post("/api/projects", json={"name": "Action routing idea"}).json()["id"]

    response = client.post(f"/api/projects/{project_id}/guide/actions/structure_idea/execute")
    assert response.status_code == 200
    action = response.json()
    assert action["type"] == "open_form"
    assert action["label"] == "Open thesis structure form"
    assert action["target_route"].endswith("#structured-intake")

    missing = client.post(f"/api/projects/{project_id}/guide/actions/not-real/execute")
    assert missing.status_code == 404


def test_guide_action_router_uses_specific_commands_and_aliases(
    client: TestClient,
) -> None:
    seed_response = client.post("/api/demo/seed")
    assert seed_response.status_code == 200
    project_id = seed_response.json()["project"]["id"]

    recommend = _guide_recommend(client, project_id)
    assert recommend["recommended_action"]["id"] == "use_suggested_decision"
    assert recommend["recommended_action"]["label"] == "Prepare decision record"
    assert recommend["recommended_action"]["target_modal"] == "record-decision-panel"
    assert len(recommend["secondary_actions"]) <= 3
    assert recommend["after_that"].startswith("The decision trail")

    actions_response = client.get(f"/api/projects/{project_id}/guide/context")
    assert actions_response.status_code == 200
    action_labels = {
        action["id"]: action["label"] for action in actions_response.json()["available_actions"]
    }
    assert action_labels["show_blocker_evidence"] == "Show evidence behind the blocker"
    assert action_labels["rewrite_thesis_with_wedge"] == "Rewrite thesis with current wedge"
    assert action_labels["compare_wedge_options"] == "Compare wedge options"
    assert "Show evidence" not in action_labels.values()
    assert "Improve thesis" not in action_labels.values()

    old_alias = client.post(f"/api/projects/{project_id}/guide/actions/show_evidence/execute")
    assert old_alias.status_code == 200
    assert old_alias.json()["id"] == "show_blocker_evidence"


def test_guide_chat_is_project_scoped_and_rejects_generic_questions(client: TestClient) -> None:
    project_id = client.post("/api/projects", json={"name": "Chat guide idea"}).json()["id"]

    next_response = client.post(
        f"/api/projects/{project_id}/guide/chat",
        json={"message": "What should I do next?"},
    )
    assert next_response.status_code == 200
    next_body = next_response.json()
    assert "open thesis structure form" in next_body["answer"].lower()
    assert next_body["recommended_action"]["id"] == "structure_idea"
    assert next_body["action_cards"]
    assert next_body["related_entities"][0]["type"] == "thesis"

    form_response = client.post(
        f"/api/projects/{project_id}/guide/chat",
        json={"message": "Open the right form."},
    )
    assert form_response.status_code == 200
    assert form_response.json()["recommended_action"]["target_modal"] == "structured-intake"

    off_topic = client.post(
        f"/api/projects/{project_id}/guide/chat",
        json={"message": "Write me a recipe for dinner."},
    )
    assert off_topic.status_code == 200
    off_topic_body = off_topic.json()
    assert "I can help with this idea's thesis" in off_topic_body["answer"]
    assert off_topic_body["action_cards"]


def test_guide_explains_idea_story_wedge_and_next_proof(client: TestClient) -> None:
    project_id = _project_with_story(client)

    wedge_response = client.post(
        f"/api/projects/{project_id}/guide/chat",
        json={"message": "Why did you recommend this wedge?"},
    )
    assert wedge_response.status_code == 200
    wedge_body = wedge_response.json()
    assert "Recommended wedge" in wedge_body["answer"]
    assert "First test" in wedge_body["answer"]
    assert wedge_body["recommended_action"]["id"] == "compare_wedge_options"

    rejected_response = client.post(
        f"/api/projects/{project_id}/guide/chat",
        json={"message": "Why did we reject the broad version?"},
    )
    assert rejected_response.status_code == 200
    rejected_body = rejected_response.json()
    assert "Rejected directions" in rejected_body["answer"]
    assert rejected_body["recommended_action"]["id"] == "show_idea_story"

    proof_response = client.post(
        f"/api/projects/{project_id}/guide/chat",
        json={"message": "What is the next proof?"},
    )
    assert proof_response.status_code == 200
    proof_body = proof_response.json()
    assert "The next proof is" in proof_body["answer"]
    assert "current blocker" in proof_body["answer"]
    assert any(action["id"] == "show_idea_story" for action in proof_body["action_cards"])


def _guide_context(client: TestClient, project_id: str) -> dict:
    response = client.get(f"/api/projects/{project_id}/guide/context")
    assert response.status_code == 200
    return response.json()


def _guide_recommend(client: TestClient, project_id: str) -> dict:
    response = client.post(f"/api/projects/{project_id}/guide/recommend")
    assert response.status_code == 200
    return response.json()


def _project_with_story(client: TestClient) -> str:
    project_id = client.post(
        "/api/projects",
        json={"name": "Story guide idea"},
    ).json()["id"]
    finalize = client.post(
        f"/api/projects/{project_id}/intake/finalize",
        json={
            "raw_idea": "A broad AI platform for independent fitness coaches.",
            "answers": [],
            "structured_intake": {
                "project_name": "Story guide idea",
                "one_sentence_summary": (
                    "Independent online fitness coaches need cited weekly check-in triage."
                ),
                "target_users": ["Independent online fitness coaches"],
                "buyer_type": "prosumer",
                "problem_hypotheses": [
                    "Coaches lose time finding which clients need attention first."
                ],
                "proposed_solution": "Cited weekly check-in triage for coaches.",
                "market_category": "Fitness coaching software",
                "business_model_guess": "Subscription",
                "suspected_competitors": ["Trainerize", "TrueCoach"],
                "key_uncertainties": ["Will coaches trust and pay for AI recommendations?"],
                "clarifying_questions": [],
            },
        },
    )
    assert finalize.status_code == 200
    generated = client.post(f"/api/projects/{project_id}/wedges/generate")
    assert generated.status_code == 200
    wedges = generated.json()["wedges"]
    recommended = next(wedge for wedge in wedges if wedge["recommendation"] == "recommended")
    avoid = next(wedge for wedge in wedges if wedge["recommendation"] == "avoid_for_now")
    test_response = client.post(f"/api/projects/{project_id}/wedges/{recommended['id']}/test")
    assert test_response.status_code == 200
    reject_response = client.post(f"/api/projects/{project_id}/wedges/{avoid['id']}/reject")
    assert reject_response.status_code == 200
    return project_id
