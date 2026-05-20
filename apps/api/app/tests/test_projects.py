from fastapi.testclient import TestClient


def test_project_crud_creates_first_thesis(client: TestClient) -> None:
    create_response = client.post(
        "/api/projects",
        json={
            "name": "Adaptive coaching",
            "short_description": "AI workflow for independent fitness coaches.",
            "initial_thesis": "Coaches need a better way to turn check-ins into actions.",
        },
    )

    assert create_response.status_code == 201
    created = create_response.json()
    assert created["name"] == "Adaptive coaching"
    assert created["workspace_id"]
    assert created["current_thesis"]["version"] == 1
    assert created["current_thesis"]["thesis_text"] == (
        "Coaches need a better way to turn check-ins into actions."
    )

    list_response = client.get("/api/projects")
    assert list_response.status_code == 200
    assert [project["id"] for project in list_response.json()["projects"]] == [created["id"]]

    update_response = client.patch(
        f"/api/projects/{created['id']}",
        json={"status": "paused", "short_description": "Narrower ICP test."},
    )
    assert update_response.status_code == 200
    assert update_response.json()["status"] == "paused"
    assert update_response.json()["short_description"] == "Narrower ICP test."

    delete_response = client.delete(f"/api/projects/{created['id']}")
    assert delete_response.status_code == 204

    assert client.get("/api/projects").json()["projects"] == []


def test_projects_are_scoped_to_workspace(client: TestClient) -> None:
    user_a_headers = {"X-Dev-User-Email": "a@example.com", "X-Dev-User-Name": "User A"}
    user_b_headers = {"X-Dev-User-Email": "b@example.com", "X-Dev-User-Name": "User B"}

    create_response = client.post(
        "/api/projects",
        headers=user_a_headers,
        json={"name": "User A project", "short_description": "Private to workspace A."},
    )
    assert create_response.status_code == 201
    project_id = create_response.json()["id"]

    user_b_list = client.get("/api/projects", headers=user_b_headers)
    assert user_b_list.status_code == 200
    assert user_b_list.json()["projects"] == []

    user_b_get = client.get(f"/api/projects/{project_id}", headers=user_b_headers)
    assert user_b_get.status_code == 404


def test_me_endpoint_returns_dev_identity(client: TestClient) -> None:
    response = client.get(
        "/api/me",
        headers={"X-Dev-User-Email": "dev@example.com", "X-Dev-User-Name": "Dev"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["user"]["email"] == "dev@example.com"
    assert body["workspace"]["name"] == "Dev's Workspace"
    assert body["role"] == "owner"
