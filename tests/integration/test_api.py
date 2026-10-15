from fastapi.testclient import TestClient
from lotus_api.main import app

client = TestClient(app)


def test_ready_is_fixture_backed() -> None:
    response = client.get("/v1/readyz")
    assert response.status_code == 200
    assert response.json()["runtime"] == "fixture"
    assert len(response.headers["X-Request-ID"]) == 12


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


def test_calendar_meeting_can_be_summarized_idempotently() -> None:
    first = client.post("/v1/meetings/M-107/summarize")
    second = client.post("/v1/meetings/M-107/summarize")
    assert first.status_code == second.status_code == 200
    assert first.json()["analysis"] == second.json()["analysis"]
    assert first.json()["transcript"]["segments"][0]["segment_id"] == "m107-s1"


def test_summarize_requires_an_authorized_transcript() -> None:
    response = client.post(
        "/v1/meetings/M-107/summarize",
        headers={"X-Lotus-Tenant": "other", "X-Lotus-User": "outsider"},
    )
    assert response.status_code == 404


def test_create_calendar_event_appears_in_list() -> None:
    created = client.post(
        "/v1/calendar/events",
        json={
            "title": "API test sync",
            "started_at": "2026-10-14T16:00:00+05:30",
            "ended_at": "2026-10-14T16:30:00+05:30",
            "description": "Created from integration test",
            "video_meeting": True,
        },
    )
    assert created.status_code == 200
    body = created.json()
    listing = client.get(
        "/v1/calendar/events",
        params={
            "project_id": "payments",
            "date_from": "2026-10-14T00:00:00+05:30",
            "date_to": "2026-10-15T00:00:00+05:30",
        },
    )
    assert any(row["event_id"] == body["event_id"] for row in listing.json())


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
    assert len(events) >= 10
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
