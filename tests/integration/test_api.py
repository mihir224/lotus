from fastapi.testclient import TestClient
from lotus_api.main import app

client = TestClient(app)


def test_ready_is_fixture_backed() -> None:
    response = client.get("/v1/readyz")
    assert response.status_code == 200
    assert response.json()["mode"] == "fixture"


def test_grounded_answer_contains_scope_and_evidence() -> None:
    response = client.post(
        "/v1/chat/messages",
        headers={"X-Lotus-Tenant": "demo", "X-Lotus-User": "alice"},
        json={
            "message": "Why are checkout retries capped, and what should on-call do?",
            "project_id": "payments",
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["route"]["route"] == "knowledge"
    assert body["scope"]["tenant_id"] == "demo"
    assert len(body["evidence"]) >= 2


def test_no_answer_abstains() -> None:
    response = client.post(
        "/v1/chat/messages",
        json={"message": "What is the lunar office dress code?", "project_id": "payments"},
    )
    assert response.status_code == 200
    assert response.json()["evidence"] == []
    assert "could not verify" in response.json()["answer"]
