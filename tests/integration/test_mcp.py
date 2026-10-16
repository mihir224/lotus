import json

import pytest
from fastapi.testclient import TestClient
from lotus_api.main import app
from lotus_api.mcp_servers import register_run_context, release_run_context
from lotus_api.models import AuthContext, ChatRequest


@pytest.fixture(scope="module")
def scoped_client():
    with TestClient(app, base_url="http://127.0.0.1:8000") as client:
        yield client


def test_planner_mcp_is_scoped_and_uses_streamable_http(scoped_client: TestClient) -> None:
    context_id, headers = register_run_context(
        AuthContext(tenant_id="demo", user_id="mcp-test", principals=("group:demo",)),
        ChatRequest(message="Who owns payments?", project_id="payments"),
    )
    headers.update(
        {
            "accept": "application/json, text/event-stream",
            "content-type": "application/json",
            "mcp-protocol-version": "2025-11-25",
        }
    )
    try:
        response = scoped_client.post(
            "/internal/mcp/planner/",
            headers=headers,
            json={
                "jsonrpc": "2.0",
                "id": 1,
                "method": "tools/call",
                "params": {
                    "name": "get_project_stakeholders",
                    "arguments": {"project_id": "payments"},
                },
            },
        )
        assert response.status_code == 200
        assert "mihir.saini@lotus.example" in response.text
        unauthorized = scoped_client.post(
            "/internal/mcp/planner/",
            headers={
                "accept": "application/json, text/event-stream",
                "content-type": "application/json",
                "mcp-protocol-version": "2025-11-25",
            },
            json={
                "jsonrpc": "2.0",
                "id": 2,
                "method": "tools/call",
                "params": {
                    "name": "get_project_stakeholders",
                    "arguments": {"project_id": "payments"},
                },
            },
        )
        assert unauthorized.status_code == 200
        assert unauthorized.json()["result"]["isError"] is True

        filtered = scoped_client.post(
            "/internal/mcp/planner/",
            headers=headers,
            json={
                "jsonrpc": "2.0",
                "id": 3,
                "method": "tools/call",
                "params": {
                    "name": "search_planning_items",
                    "arguments": {"query": "", "status": "testing"},
                },
            },
        )
        filtered_payload = json.loads(filtered.json()["result"]["content"][0]["text"])
        assert filtered_payload["count"] > 0
        assert all(
            row["status"] == "testing" for row in filtered_payload["planning_items"]
        )

        documents = scoped_client.post(
            "/internal/mcp/documents/",
            headers=headers,
            json={
                "jsonrpc": "2.0",
                "id": 4,
                "method": "tools/call",
                "params": {
                    "name": "list_documents",
                    "arguments": {"query": "", "team": "Security"},
                },
            },
        )
        document_payload = json.loads(documents.json()["result"]["content"][0]["text"])
        assert document_payload["count"] > 0
        assert all(row["team"] == "Security" for row in document_payload["documents"])
        assert "embedding" not in documents.text
        assert "chunk_text" not in documents.text
    finally:
        release_run_context(context_id)


def test_calendar_mcp_lists_recent_meetings_without_transcript_search(
    scoped_client: TestClient,
) -> None:
    context_id, headers = register_run_context(
        AuthContext(tenant_id="demo", user_id="mcp-test", principals=("group:demo",)),
        ChatRequest(message="Give me details about my last meeting", project_id="payments"),
    )
    headers.update(
        {
            "accept": "application/json, text/event-stream",
            "content-type": "application/json",
            "mcp-protocol-version": "2025-11-25",
        }
    )
    try:
        response = scoped_client.post(
            "/internal/mcp/calendar/",
            headers=headers,
            json={
                "jsonrpc": "2.0",
                "id": 1,
                "method": "tools/call",
                "params": {"name": "search_meetings", "arguments": {"query": ""}},
            },
        )
        assert response.status_code == 200
        text = response.json()["result"]["content"][0]["text"]
        assert '"meetings"' in text
        assert '"embedding"' not in text
        assert '"retrieval_method"' not in text

        dated = scoped_client.post(
            "/internal/mcp/calendar/",
            headers=headers,
            json={
                "jsonrpc": "2.0",
                "id": 2,
                "method": "tools/call",
                "params": {
                    "name": "search_meetings",
                    "arguments": {
                        "query": "",
                        "date_from": "2026-10-14T00:00:00+05:30",
                        "date_to": "2026-10-15T00:00:00+05:30",
                    },
                },
            },
        )
        dated_payload = json.loads(dated.json()["result"]["content"][0]["text"])
        assert dated_payload["count"] == len(dated_payload["meetings"])
        assert dated_payload["count"] >= 2
        assert all(
            row["started_at"].startswith("2026-10-14")
            for row in dated_payload["meetings"]
        )
    finally:
        release_run_context(context_id)
