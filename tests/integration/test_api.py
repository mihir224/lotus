from fastapi.testclient import TestClient
from lotus_api.main import app

client = TestClient(app)


def test_ready_is_fixture_backed() -> None:
    response = client.get("/v1/readyz")
    assert response.status_code == 200
    assert response.json()["runtime"] == "fixture"
    assert len(response.headers["X-Request-ID"]) == 12


def test_ready_returns_503_when_store_is_unavailable(monkeypatch) -> None:
    class UnavailableStore:
        @staticmethod
        def ready() -> bool:
            return False

    monkeypatch.setattr("lotus_api.main.get_store", lambda: UnavailableStore())
    response = client.get("/v1/readyz")
    assert response.status_code == 503
    assert response.json()["status"] == "not_ready"


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
    assert body["agents_used"] == ["documents", "result"]
    assert body["session_id"]
    assert any(row["navigation_target"]["kind"] == "document" for row in body["evidence"])


def test_chat_history_is_persistent_and_user_scoped() -> None:
    created = client.post(
        "/v1/chat/sessions",
        headers={"X-Lotus-User": "history-owner"},
        json={"project_id": "payments"},
    )
    assert created.status_code == 200
    session_id = created.json()["session_id"]
    answer = client.post(
        "/v1/chat/messages",
        headers={"X-Lotus-User": "history-owner"},
        json={
            "message": "Show the checkout retry architecture",
            "project_id": "payments",
            "session_id": session_id,
        },
    )
    assert answer.status_code == 200
    detail = client.get(
        f"/v1/chat/sessions/{session_id}", headers={"X-Lotus-User": "history-owner"}
    )
    assert [row["role"] for row in detail.json()["messages"]] == ["user", "assistant"]
    assert client.get(
        f"/v1/chat/sessions/{session_id}", headers={"X-Lotus-User": "another-user"}
    ).status_code == 404
    assert client.delete(
        f"/v1/chat/sessions/{session_id}", headers={"X-Lotus-User": "history-owner"}
    ).status_code == 204
    assert client.get(
        f"/v1/chat/sessions/{session_id}", headers={"X-Lotus-User": "history-owner"}
    ).status_code == 404


def test_project_stakeholder_question_uses_planning_evidence() -> None:
    response = client.post(
        "/v1/chat/messages",
        json={"message": "Who are the stakeholders for this project?", "project_id": "payments"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["agents_used"] == ["planning", "result"]
    assert "mihir.saini@lotus.example" in body["evidence"][0]["snippet"]
    assert body["navigation_targets"][0]["kind"] == "project"


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
    assert "clarifications_needed" in first.json()["analysis"]


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


def test_work_board_lists_and_updates_issue() -> None:
    board = client.get("/v1/work-board", params={"project_id": "payments", "team_id": "platform"})
    assert board.status_code == 200
    body = board.json()
    assert body["board"]["board_title"] == "Delivery board"
    assert len(body["issues"]) == 15
    patched = client.patch(
        "/v1/work-board/issues/PROJ-101",
        json={"status": "development"},
    )
    assert patched.status_code == 200
    assert patched.json()["status"] == "development"
    again = client.get("/v1/work-board", params={"team_id": "platform"})
    match = next(row for row in again.json()["issues"] if row["issue_key"] == "PROJ-101")
    assert match["status"] == "development"


def test_docs_catalog_search_and_create() -> None:
    catalog = client.get("/v1/docs/catalog", params={"project_id": "payments"})
    assert catalog.status_code == 200
    groups = catalog.json()["groups"]
    assert len(groups) >= 1
    total_pages = sum(len(group["pages"]) for group in groups)
    assert total_pages >= 10

    search = client.get(
        "/v1/docs/search",
        params={"project_id": "payments", "q": "retry"},
    )
    assert search.status_code == 200
    assert len(search.json()) >= 1

    detail = client.get(
        "/v1/docs/sources/ADR-017",
        params={"project_id": "payments"},
    )
    assert detail.status_code == 200
    assert "jitter" in detail.json()["body"].casefold()

    created = client.post(
        "/v1/docs/sources",
        json={
            "project_id": "payments",
            "title": "Lotus onboarding note",
            "team": "Platform",
            "source_type": "guide",
            "body": "New hires should read the checkout runbooks first.",
        },
    )
    assert created.status_code == 200
    source_id = created.json()["source_id"]
    assert source_id.startswith("LOTUS-")

    again = client.get("/v1/docs/catalog", params={"project_id": "payments"})
    ids = {
        page["source_id"]
        for group in again.json()["groups"]
        for page in group["pages"]
    }
    assert source_id in ids


def test_create_work_board_issue() -> None:
    created = client.post(
        "/v1/work-board/issues",
        json={
            "title": "New trace dashboard",
            "project_id": "payments",
            "team_id": "platform",
            "feature_key": "PROJ-42",
            "assignee_id": "unassigned",
            "reporter_id": "unassigned",
        },
    )
    assert created.status_code == 200
    body = created.json()
    assert body["issue_key"] == "PROJ-116"
    assert body["feature_title"] == "Standardize observability across services"
    assert body["status"] == "ready_to_start"
    assert body["assignee_id"] == "unassigned"
    board = client.get("/v1/work-board", params={"team_id": "platform"})
    keys = {row["issue_key"] for row in board.json()["issues"]}
    assert "PROJ-116" in keys


def test_no_answer_abstains() -> None:
    response = client.post(
        "/v1/chat/messages",
        json={"message": "What is the lunar office dress code?", "project_id": "payments"},
    )
    assert response.status_code == 200
    assert response.json()["evidence"] == []
    assert "could not verify" in response.json()["answer"]
