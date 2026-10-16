from fastapi.testclient import TestClient
from lotus_api.main import app
from lotus_api.mcp_servers import register_run_context, release_run_context
from lotus_api.models import AuthContext, ChatRequest


def test_planner_mcp_is_scoped_and_uses_streamable_http() -> None:
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
        with TestClient(app, base_url="http://127.0.0.1:8000") as scoped_client:
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
    finally:
        release_run_context(context_id)
