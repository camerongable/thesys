from fastapi.testclient import TestClient


def test_thesis_canvas_is_seeded_from_structured_intake(client: TestClient) -> None:
    project_id = client.post("/api/projects", json={"name": "Plant idea"}).json()["id"]
    structured_intake = {
        "project_name": "Plant Parenthood",
        "one_sentence_summary": "Beginner plant owners need clearer care guidance.",
        "target_users": ["Beginner plant owners"],
        "buyer_type": "consumer",
        "problem_hypotheses": ["Plant-care advice is fragmented and hard to apply."],
        "proposed_solution": "A guided troubleshooting workflow for sick houseplants.",
        "market_category": "Plant care",
        "business_model_guess": "Subscription",
        "suspected_competitors": ["Plant care apps", "Reddit"],
        "key_uncertainties": [
            "Will users pay for guidance?",
            "Which plant problem is most urgent?",
        ],
        "clarifying_questions": ["What current workaround do they use?"],
    }
    finalize = client.post(
        f"/api/projects/{project_id}/intake/finalize",
        json={
            "structured_intake": structured_intake,
            "raw_idea": "A place to learn about plants.",
            "answers": [],
        },
    )
    assert finalize.status_code == 200

    response = client.get(f"/api/projects/{project_id}/thesis-canvas")
    assert response.status_code == 200
    body = response.json()
    canvas = body["canvas"]
    assert canvas["original_idea"] == "A place to learn about plants."
    assert canvas["current_thesis"] == "Beginner plant owners need clearer care guidance."
    assert canvas["target_user"] == "Beginner plant owners"
    assert canvas["problem"] == "Plant-care advice is fragmented and hard to apply."
    assert canvas["proposed_solution"] == "A guided troubleshooting workflow for sick houseplants."
    assert "Will users pay for guidance?" in canvas["open_questions"]

    evolution_titles = [event["title"] for event in body["evolution"]]
    assert "Original idea captured" in evolution_titles
    assert "Structured thesis created" in evolution_titles


def test_thesis_canvas_update_versions_current_thesis_and_records_evolution(
    client: TestClient,
) -> None:
    create = client.post(
        "/api/projects",
        json={
            "name": "Coach idea",
            "short_description": "AI support for coaches.",
            "initial_thesis": "Coaches need faster check-in synthesis.",
        },
    )
    project_id = create.json()["id"]

    update = client.patch(
        f"/api/projects/{project_id}/thesis-canvas",
        json={
            "current_thesis": (
                "Independent online coaches need at-risk client triage before weekly calls."
            ),
            "wedge": "At-risk client triage",
            "biggest_unknown": "Will coaches pay for automated triage?",
            "proof_needed": "Five coaches agree to a paid pilot.",
            "rejected_directions": ["Generic workout plan generator"],
            "open_questions": ["Which coaching niche has the strongest urgency?"],
            "change_reason": "Narrowed from broad coach support to the riskiest workflow.",
        },
    )
    assert update.status_code == 200
    body = update.json()
    assert body["canvas"]["current_thesis"].startswith("Independent online coaches")
    assert body["canvas"]["rejected_directions"] == ["Generic workout plan generator"]
    assert body["evolution"][-1]["title"] == "Thesis canvas updated"
    assert "Narrowed from broad coach support" in body["evolution"][-1]["reason"]

    project = client.get(f"/api/projects/{project_id}").json()
    assert project["current_thesis"]["version"] == 2
    assert project["current_thesis"]["thesis_text"].startswith("Independent online coaches")


def test_thesis_evolution_includes_validation_and_guide_can_explain_change(
    client: TestClient,
) -> None:
    project_id = client.post(
        "/api/projects",
        json={
            "name": "Validation idea",
            "initial_thesis": "Founders need a validation copilot.",
        },
    ).json()["id"]

    assumptions = client.post(f"/api/projects/{project_id}/assumptions/extract")
    assert assumptions.status_code == 200

    evolution = client.get(f"/api/projects/{project_id}/thesis-evolution")
    assert evolution.status_code == 200
    titles = [event["title"] for event in evolution.json()]
    assert "Biggest unknown identified" in titles

    chat = client.post(
        f"/api/projects/{project_id}/guide/chat",
        json={"message": "How has this idea evolved and what directions were rejected?"},
    )
    assert chat.status_code == 200
    body = chat.json()
    assert "The idea started as" in body["answer"]
    assert body["recommended_action"]["id"] == "show_idea_story"
    assert any(action["id"] == "show_idea_story" for action in body["action_cards"])


def test_idea_story_summarizes_growth_from_original_to_next_proof(
    client: TestClient,
) -> None:
    project_id = client.post("/api/projects", json={"name": "Fitness coach assistant"}).json()[
        "id"
    ]
    finalize = client.post(
        f"/api/projects/{project_id}/intake/finalize",
        json={
            "raw_idea": "A broad AI platform for online fitness coaches.",
            "answers": [],
            "structured_intake": {
                "project_name": "Fitness coach assistant",
                "one_sentence_summary": (
                    "Independent online fitness coaches need faster at-risk client triage."
                ),
                "target_users": ["Independent online fitness coaches"],
                "buyer_type": "prosumer",
                "problem_hypotheses": [
                    "Coaches lose time reviewing check-ins across DMs and spreadsheets."
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

    story = client.get(f"/api/projects/{project_id}/idea-story")
    assert story.status_code == 200
    body = story.json()
    assert body["original_idea"] == "A broad AI platform for online fitness coaches."
    assert body["current_thesis"] == (
        "Independent online fitness coaches need faster at-risk client triage."
    )
    assert body["selected_wedge"] == recommended["name"]
    assert avoid["name"] in body["rejected_directions"]
    assert body["current_blocker"] == recommended["main_risk"]
    assert body["next_proof"] == recommended["validation_test"]
    assert body["why_it_changed"]
