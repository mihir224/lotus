"""Internal, read-only MCP servers for Lotus workspace specialists."""

from __future__ import annotations

import secrets
import threading
from dataclasses import dataclass
from uuid import uuid4

from mcp.server.mcpserver import Context, MCPServer

from .models import AuthContext, ChatRequest
from .storage import get_store

_INTERNAL_TOKEN = secrets.token_urlsafe(32)
_contexts: dict[str, McpRunContext] = {}
_lock = threading.Lock()


@dataclass(frozen=True)
class McpRunContext:
    auth: AuthContext
    request: ChatRequest


def register_run_context(auth: AuthContext, request: ChatRequest) -> tuple[str, dict[str, str]]:
    context_id = uuid4().hex
    with _lock:
        _contexts[context_id] = McpRunContext(auth=auth, request=request)
    return context_id, {
        "X-Lotus-Internal-MCP": _INTERNAL_TOKEN,
        "X-Lotus-Run-Context": context_id,
    }


def release_run_context(context_id: str) -> None:
    with _lock:
        _contexts.pop(context_id, None)


def _run_context(ctx: Context) -> McpRunContext:
    headers = {key.casefold(): value for key, value in ctx.headers.items()}
    if headers.get("x-lotus-internal-mcp") != _INTERNAL_TOKEN:
        raise PermissionError("Internal MCP authentication failed")
    context_id = headers.get("x-lotus-run-context", "")
    with _lock:
        run = _contexts.get(context_id)
    if run is None:
        raise PermissionError("MCP run context is missing or expired")
    return run


def _bounded_evidence(rows) -> list[dict]:
    result = []
    for row in rows[:8]:
        payload = row.model_dump(mode="json")
        payload["snippet"] = payload["snippet"][:1_500]
        result.append(payload)
    return result


planner_mcp = MCPServer(
    "lotus-planner-mcp",
    instructions="Read-only access to authorized Lotus projects, planning items, and stakeholders.",
)
calendar_mcp = MCPServer(
    "lotus-calendar-mcp",
    instructions="Read-only access to authorized calendar meetings and transcript metadata.",
)
documents_mcp = MCPServer(
    "lotus-documents-mcp",
    instructions="Read-only access to authorized Lotus documents.",
)


@planner_mcp.tool()
def get_project(project_id: str, ctx: Context) -> dict:
    """Get one authorized workspace project and its stakeholders by project ID."""
    run = _run_context(ctx)
    project = get_store().get_workspace_project(project_id, run.auth)
    return {"project": project.model_dump(mode="json") if project else None}


@planner_mcp.tool()
def get_planning_item(item_id: str, ctx: Context) -> dict:
    """Get one authorized planning item by issue key."""
    run = _run_context(ctx)
    rows = get_store().list_board_issues(run.auth, run.request.project_id)
    item = next((row for row in rows if row.issue_key.casefold() == item_id.casefold()), None)
    return {"planning_item": item.model_dump(mode="json") if item else None}


@planner_mcp.tool()
def get_project_stakeholders(project_id: str, ctx: Context) -> dict:
    """List authorized stakeholders and work contact details for a project."""
    run = _run_context(ctx)
    project = get_store().get_workspace_project(project_id, run.auth)
    return {
        "project_id": project_id,
        "stakeholders": (
            [row.model_dump(mode="json") for row in project.stakeholders] if project else []
        ),
    }


@calendar_mcp.tool()
def get_meeting(meeting_id: str, ctx: Context) -> dict:
    """Get one authorized meeting, its bounded transcript, and analysis."""
    run = _run_context(ctx)
    record = get_store().get_meeting(meeting_id, run.auth)
    if record is None:
        return {"meeting": None}
    payload = record.model_dump(mode="json")
    payload["transcript"]["segments"] = [
        {**segment, "text": segment["text"][:1_500]}
        for segment in payload["transcript"]["segments"][:40]
    ]
    return {"meeting": payload}


@calendar_mcp.tool()
def search_meetings(query: str, ctx: Context) -> dict:
    """Search authorized meeting transcript chunks using the current project scope."""
    run = _run_context(ctx)
    rows = get_store().search_transcripts(
        query,
        run.auth,
        run.request.project_id,
        top_k=8,
        meeting_id=run.request.meeting_id,
    )
    return {"evidence": _bounded_evidence(rows)}


@documents_mcp.tool()
def get_document(document_id: str, ctx: Context) -> dict:
    """Get an authorized document by source ID."""
    run = _run_context(ctx)
    rows = get_store().list_knowledge_document_chunks(run.auth, run.request.project_id)
    matches = [row for row in rows if row["source_id"].casefold() == document_id.casefold()]
    return {
        "document": [
            {**row, "chunk_text": row["chunk_text"][:1_500]}
            for row in matches[:12]
        ]
    }


@documents_mcp.tool()
def search_documents(query: str, ctx: Context) -> dict:
    """Search authorized document chunks using the current project scope."""
    run = _run_context(ctx)
    rows = get_store().search_documents(query, run.auth, run.request.project_id, top_k=8)
    return {"evidence": _bounded_evidence(rows)}


planner_mcp_app = planner_mcp.streamable_http_app(
    streamable_http_path="/", stateless_http=True, json_response=True, max_sessions=32
)
calendar_mcp_app = calendar_mcp.streamable_http_app(
    streamable_http_path="/", stateless_http=True, json_response=True, max_sessions=32
)
documents_mcp_app = documents_mcp.streamable_http_app(
    streamable_http_path="/", stateless_http=True, json_response=True, max_sessions=32
)
