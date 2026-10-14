from fastapi.testclient import TestClient
from lotus_api.main import app

client = TestClient(app)


def test_ready_is_fixture_backed() -> None:
    response = client.get("/v1/readyz")
    assert response.status_code == 200
    assert response.json()["runtime"] == "fixture"


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
    assert body["agents_used"] == ["data", "result"]


def test_meeting_search_returns_timestamped_transcript_link() -> None:
    response = client.post(
        "/v1/chat/messages",
        json={
            "message": "Which meeting discussed retry jitter last week?",
            "project_id": "payments",
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["agents_used"] == ["meeting", "result"]
    assert any(
        row["meeting_id"] == "M-104" and row["start_ms"] is not None
        for row in body["evidence"]
    )


def test_meeting_endpoints_return_transcript_and_analysis() -> None:
    listing = client.get("/v1/meetings?project_id=payments")
    assert listing.status_code == 200
    meeting_ids = {row["meeting_id"] for row in listing.json()}
    assert "M-104" in meeting_ids
    assert len(meeting_ids) >= 3
    detail = client.get("/v1/meetings/M-104")
    assert detail.status_code == 200
    assert detail.json()["analysis"]["decisions"]


def test_calendar_events_fixture_week() -> None:
    response = client.get(
        "/v1/calendar/events",
        params={
            "project_id": "payments",
            "date_from": "2026-10-12T00:00:00+05:30",
            "date_to": "2026-10-17T00:00:00+05:30",
        },
    )
    assert response.status_code == 200
    events = response.json()
    assert len(events) == 10
    assert events[0]["meeting_id"] == "M-107"
    assert all(row["event_id"].startswith("cal-") for row in events)


def test_no_answer_abstains() -> None:
    response = client.post(
        "/v1/chat/messages",
        json={"message": "What is the lunar office dress code?", "project_id": "payments"},
    )
    assert response.status_code == 200
    assert response.json()["evidence"] == []
    assert "could not verify" in response.json()["answer"]
