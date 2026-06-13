from fastapi.testclient import TestClient


def test_wedge_options_can_be_generated_from_project_state(client: TestClient) -> None:
    project_id = _project_with_intake(client)

    empty = client.get(f"/api/projects/{project_id}/wedges")
    assert empty.status_code == 200
    assert empty.json()["wedges"] == []

    generated = client.post(f"/api/projects/{project_id}/wedges/generate")
    assert generated.status_code == 200
    body = generated.json()
    assert len(body["wedges"]) >= 3
    assert body["recommended_wedge_id"] is not None
    assert "Recommended wedge" in body["recommendation_summary"]

    recommended = next(
        wedge for wedge in body["wedges"] if wedge["id"] == body["recommended_wedge_id"]
    )
    assert recommended["recommendation"] == "recommended"
    assert recommended["target_user"] == "Independent online fitness coaches"
    assert recommended["validation_test"]


def test_selecting_wedge_updates_thesis_canvas_and_evolution(client: TestClient) -> None:
    project_id = _project_with_intake(client)
    wedges = client.post(f"/api/projects/{project_id}/wedges/generate").json()["wedges"]
    selected = wedges[1]

    response = client.post(f"/api/projects/{project_id}/wedges/{selected['id']}/select")
    assert response.status_code == 200
    assert "selected wedge" in response.json()["message"]

    canvas = client.get(f"/api/projects/{project_id}/thesis-canvas").json()
    assert canvas["canvas"]["wedge"] == selected["name"]
    assert canvas["canvas"]["target_user"] == selected["target_user"]
    assert canvas["canvas"]["proof_needed"] == selected["validation_test"]
    assert canvas["evolution"][-1]["event_type"] == "wedge_change"
    assert canvas["evolution"][-1]["title"] == "Wedge selected"

    updated_wedges = client.get(f"/api/projects/{project_id}/wedges").json()
    recommended = [
        wedge for wedge in updated_wedges["wedges"] if wedge["recommendation"] == "recommended"
    ]
    assert [wedge["id"] for wedge in recommended] == [selected["id"]]


def test_rejecting_wedge_preserves_rejected_direction(client: TestClient) -> None:
    project_id = _project_with_intake(client)
    wedges = client.post(f"/api/projects/{project_id}/wedges/generate").json()["wedges"]
    rejected = wedges[-1]

    response = client.post(f"/api/projects/{project_id}/wedges/{rejected['id']}/reject")
    assert response.status_code == 200
    assert response.json()["wedge"]["recommendation"] == "rejected"

    canvas = client.get(f"/api/projects/{project_id}/thesis-canvas").json()["canvas"]
    assert rejected["name"] in canvas["rejected_directions"]


def test_testing_wedge_sets_proof_and_guide_can_explain_recommendation(
    client: TestClient,
) -> None:
    project_id = _project_with_intake(client)
    generated = client.post(f"/api/projects/{project_id}/wedges/generate").json()
    wedge_id = generated["recommended_wedge_id"]

    test_response = client.post(f"/api/projects/{project_id}/wedges/{wedge_id}/test")
    assert test_response.status_code == 200
    assert "ready to test" in test_response.json()["message"]

    updated_wedges = client.get(f"/api/projects/{project_id}/wedges").json()
    recommended = [
        wedge for wedge in updated_wedges["wedges"] if wedge["recommendation"] == "recommended"
    ]
    assert [wedge["id"] for wedge in recommended] == [wedge_id]

    guide = client.post(
        f"/api/projects/{project_id}/guide/chat",
        json={"message": "What wedge should I choose and why?"},
    )
    assert guide.status_code == 200
    body = guide.json()
    assert "Recommended wedge" in body["answer"]
    assert any(action["id"] == "compare_wedges" for action in body["action_cards"])

    context = client.get(f"/api/projects/{project_id}/guide/context").json()
    compare = next(
        action for action in context["available_actions"] if action["id"] == "compare_wedges"
    )
    assert compare["target_route"].endswith("#wedge-explorer")


def _project_with_intake(client: TestClient) -> str:
    project_id = client.post(
        "/api/projects",
        json={"name": "Fitness coach assistant"},
    ).json()["id"]
    finalize = client.post(
        f"/api/projects/{project_id}/intake/finalize",
        json={
            "raw_idea": (
                "An AI assistant that helps independent fitness coaches manage client "
                "check-ins and decide who needs attention."
            ),
            "answers": [],
            "structured_intake": {
                "project_name": "Fitness coach assistant",
                "one_sentence_summary": (
                    "Independent fitness coaches need faster at-risk client triage."
                ),
                "target_users": ["Independent online fitness coaches"],
                "buyer_type": "prosumer",
                "problem_hypotheses": [
                    "Coaches lose time reviewing check-ins across DMs and spreadsheets."
                ],
                "proposed_solution": (
                    "An at-risk client triage workflow that summarizes check-ins before "
                    "weekly coach reviews."
                ),
                "market_category": "Fitness coaching software",
                "business_model_guess": "Subscription",
                "suspected_competitors": ["Trainerize", "TrueCoach"],
                "key_uncertainties": ["Will coaches pay for automated triage?"],
                "clarifying_questions": [],
            },
        },
    )
    assert finalize.status_code == 200
    evidence = client.post(
        f"/api/projects/{project_id}/evidence/note",
        json={
            "title": "Coach interview notes",
            "text": (
                "Coaches spend Sunday nights reviewing client check-ins and chasing missed "
                "replies."
            ),
        },
    )
    assert evidence.status_code == 201
    return project_id
