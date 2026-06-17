from fastapi.testclient import TestClient


def test_new_project_has_no_proactive_nudges(client: TestClient) -> None:
    project_id = client.post("/api/projects", json={"name": "Quiet new idea"}).json()["id"]

    response = client.get(f"/api/projects/{project_id}/nudges")

    assert response.status_code == 200
    assert response.json()["nudges"] == []


def test_research_ready_project_surfaces_actionable_nudges_and_dismisses_them(
    client: TestClient,
) -> None:
    project_id = client.post(
        "/api/projects",
        json={
            "name": "Fitness coach triage",
            "short_description": "AI triage for online coach check-ins.",
        },
    ).json()["id"]
    for title, text in [
        (
            "Coach interview",
            "Online fitness coaches lose hours triaging client check-ins every week.",
        ),
        (
            "Competitor note",
            "Existing coaching platforms support messaging but weakly automate risk triage.",
        ),
    ]:
        note_response = client.post(
            f"/api/projects/{project_id}/evidence/note",
            json={"title": title, "text": text},
        )
        assert note_response.status_code == 201

    extract_response = client.post(f"/api/projects/{project_id}/assumptions/extract")
    assert extract_response.status_code == 200

    response = client.get(f"/api/projects/{project_id}/nudges")

    assert response.status_code == 200
    nudges = response.json()["nudges"]
    assert 1 <= len(nudges) <= 2
    assert nudges[0]["severity"] == "action_required"
    assert nudges[0]["title"] == "You have enough research for a first validation test."
    assert nudges[0]["action"]["label"] == "Open validation mission"
    assert nudges[0]["action"]["target_route"].endswith("#validation-mission")

    dismiss_response = client.post(
        f"/api/projects/{project_id}/nudges/{nudges[0]['id']}/dismiss"
    )
    assert dismiss_response.status_code == 200
    assert dismiss_response.json()["dismissed"] is True

    refreshed = client.get(f"/api/projects/{project_id}/nudges").json()["nudges"]
    assert all(nudge["id"] != nudges[0]["id"] for nudge in refreshed)


def test_validation_plan_without_results_surfaces_log_results_nudge(
    client: TestClient,
) -> None:
    project_id = client.post("/api/projects", json={"name": "Validation nudge idea"}).json()["id"]
    extract_response = client.post(f"/api/projects/{project_id}/assumptions/extract")
    assert extract_response.status_code == 200
    assumption_id = extract_response.json()["assumptions"][0]["id"]

    plan_response = client.post(
        f"/api/projects/{project_id}/experiments/validation-plan",
        json={"assumption_ids": [assumption_id], "max_plans": 1},
    )
    assert plan_response.status_code == 200

    response = client.get(f"/api/projects/{project_id}/nudges")

    assert response.status_code == 200
    nudges = response.json()["nudges"]
    assert nudges
    result_nudge = next(
        nudge
        for nudge in nudges
        if nudge["title"] == "Your plan exists, but no results are logged."
    )
    assert result_nudge["severity"] == "action_required"
    assert result_nudge["action"]["id"] == "open_validation_result_form"
    assert result_nudge["action"]["label"] == "Open validation result form"
    assert result_nudge["action"]["target_modal"] == "log-result"
