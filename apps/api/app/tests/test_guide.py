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
    assert any(
        action["id"] == "open_validation_mission"
        and action["target_route"].endswith("#validation-mission")
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
    assert action["target_route"].endswith("#structured-intake")

    missing = client.post(f"/api/projects/{project_id}/guide/actions/not-real/execute")
    assert missing.status_code == 404


def test_guide_chat_is_project_scoped_and_rejects_generic_questions(client: TestClient) -> None:
    project_id = client.post("/api/projects", json={"name": "Chat guide idea"}).json()["id"]

    next_response = client.post(
        f"/api/projects/{project_id}/guide/chat",
        json={"message": "What should I do next?"},
    )
    assert next_response.status_code == 200
    next_body = next_response.json()
    assert "define the thesis" in next_body["answer"].lower()
    assert next_body["action_cards"]
    assert next_body["related_entities"][0]["type"] == "thesis"

    off_topic = client.post(
        f"/api/projects/{project_id}/guide/chat",
        json={"message": "Write me a recipe for dinner."},
    )
    assert off_topic.status_code == 200
    off_topic_body = off_topic.json()
    assert "I can help with this idea's thesis" in off_topic_body["answer"]
    assert off_topic_body["action_cards"]


def _guide_context(client: TestClient, project_id: str) -> dict:
    response = client.get(f"/api/projects/{project_id}/guide/context")
    assert response.status_code == 200
    return response.json()


def _guide_recommend(client: TestClient, project_id: str) -> dict:
    response = client.post(f"/api/projects/{project_id}/guide/recommend")
    assert response.status_code == 200
    return response.json()
