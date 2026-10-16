"""Internal, read-only MCP servers for Lotus workspace specialists."""

from __future__ import annotations

import secrets
import threading
from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import uuid4

from mcp.server.mcpserver import Context, MCPServer

from .calendar import is_synthetic_calendar_placeholder
from .models import AuthContext, ChatRequest, ExecutionPlan
from .storage import get_store

_INTERNAL_TOKEN = secrets.token_urlsafe(32)
_contexts: dict[str, McpRunContext] = {}
_lock = threading.Lock()


@dataclass(frozen=True)
class McpRunContext:
    auth: AuthContext
    request: ChatRequest
    plan: ExecutionPlan | None = None


def register_run_context(
    auth: AuthContext, request: ChatRequest, plan: ExecutionPlan | None = None
) -> tuple[str, dict[str, str]]:
    context_id = uuid4().hex
    with _lock:
        _contexts[context_id] = McpRunContext(auth=auth, request=request, plan=plan)
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


def _tool_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed


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
people_mcp = MCPServer(
    "lotus-people-mcp",
    instructions="Read-only access to authorized employee directory and stakeholder data.",
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
    return {"planning_item": _planning_item_payload(item, run) if item else None}


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


@people_mcp.tool()
def get_employee(employee_id: str, ctx: Context) -> dict:
    """Get one authorized employee profile by employee ID, email, handle, or exact name."""
    run = _run_context(ctx)
    normalized = employee_id.strip().casefold()
    employees = get_store().search_employees(run.auth, limit=50)
    employee = next(
        (
            row
            for row in employees
            if normalized
            in {
                row.employee_id.casefold(),
                row.email.casefold(),
                row.contact_handle.casefold(),
                row.name.casefold(),
            }
        ),
        None,
    )
    return {"employee": employee.model_dump(mode="json") if employee else None}


@people_mcp.tool()
def search_employees(
    query: str,
    ctx: Context,
    team: str | None = None,
    designation: str | None = None,
    timezone: str | None = None,
    limit: int = 20,
) -> dict:
    """Search authorized employee profiles using structured directory fields."""
    run = _run_context(ctx)
    rows = get_store().search_employees(
        run.auth,
        query=query,
        team=team,
        designation=designation,
        timezone=timezone,
        limit=limit,
    )
    return {
        "count": len(rows),
        "employees": [row.model_dump(mode="json") for row in rows],
    }


@people_mcp.tool()
def get_employee_project_stakeholders(project_id: str, ctx: Context) -> dict:
    """List authorized employee contacts associated with a project and their project roles."""
    run = _run_context(ctx)
    project = get_store().get_workspace_project(project_id, run.auth)
    return {
        "project_id": project_id,
        "project_name": project.name if project else None,
        "stakeholders": (
            [row.model_dump(mode="json") for row in project.stakeholders] if project else []
        ),
    }


@people_mcp.tool()
def find_subject_matter_experts(
    topic: str,
    ctx: Context,
    project_id: str | None = None,
    limit: int = 10,
) -> dict:
    """Find possible experts using explicit team, designation, and project-role metadata."""
    run = _run_context(ctx)
    candidates = get_store().search_employees(run.auth, query=topic, limit=limit)
    rows = [
        {"employee": row.model_dump(mode="json"), "basis": "directory field match"}
        for row in candidates
    ]
    if project_id:
        project = get_store().get_workspace_project(project_id, run.auth)
        if project:
            topic_words = set(topic.casefold().split())
            for stakeholder in project.stakeholders:
                searchable = (
                    f"{project.name} {project.description} {project.team} "
                    f"{stakeholder.role} {stakeholder.employee.designation} "
                    f"{stakeholder.employee.team}"
                ).casefold()
                if topic_words and not any(word in searchable for word in topic_words):
                    continue
                payload = stakeholder.employee.model_dump(mode="json")
                if any(row["employee"]["employee_id"] == payload["employee_id"] for row in rows):
                    continue
                rows.append(
                    {
                        "employee": payload,
                        "basis": f"{stakeholder.role} on {project.name}",
                    }
                )
    return {"topic": topic, "experts": rows[: min(max(limit, 1), 20)]}


@planner_mcp.tool()
def search_planning_items(
    query: str,
    ctx: Context,
    status: str | None = None,
    team_id: str | None = None,
    assignee_id: str | None = None,
    priority: str | None = None,
    limit: int = 20,
) -> dict:
    """Filter and count authorized planning items without semantic/vector retrieval."""
    run = _run_context(ctx)
    rows = get_store().list_board_issues(run.auth, run.request.project_id, team_id)
    if status:
        expected = status.strip().casefold().replace("-", "_").replace(" ", "_")
        rows = [row for row in rows if row.status.casefold() == expected]
    if assignee_id:
        rows = [row for row in rows if row.assignee_id.casefold() == assignee_id.casefold()]
    if priority:
        rows = [row for row in rows if row.priority.casefold() == priority.casefold()]
    normalized_query = query.strip().casefold()
    if normalized_query:
        rows = [
            row
            for row in rows
            if normalized_query
            in f"{row.issue_key} {row.title} {row.description} {row.feature_title}".casefold()
        ]
    bounded_limit = min(max(limit, 1), 50)
    employees_by_id = {
        employee.employee_id.casefold(): employee
        for employee in get_store().search_employees(run.auth, limit=100)
    }
    return {
        "count": len(rows),
        "planning_items": [
            _planning_item_payload(row, run, employees_by_id)
            for row in rows[:bounded_limit]
        ],
    }


def _planning_item_payload(item, run: McpRunContext, employees_by_id=None) -> dict:
    payload = item.model_dump(mode="json")
    payload["status_label"] = item.status.replace("_", " ").title()
    if item.assignee_id and item.assignee_id != "unassigned":
        if employees_by_id is None:
            employees_by_id = {
                employee.employee_id.casefold(): employee
                for employee in get_store().search_employees(run.auth, limit=100)
            }
        employee = employees_by_id.get(item.assignee_id.casefold())
        if employee:
            payload["assignee"] = {
                "employee_id": employee.employee_id,
                "name": employee.name,
                "designation": employee.designation,
            }
        else:
            payload["assignee"] = {
                "employee_id": item.assignee_id,
                "name": item.assignee_id.replace("-", " ").replace("_", " ").title(),
                "designation": None,
            }
    return payload


@calendar_mcp.tool()
def get_meeting(meeting_id: str, ctx: Context) -> dict:
    """Get one authorized calendar event and real transcript/analysis when available."""
    run = _run_context(ctx)
    record = get_store().get_meeting(meeting_id, run.auth)
    calendar_event = next(
        (
            event
            for event in get_store().list_calendar_events(
                run.auth, run.request.project_id
            )
            if event.meeting_id == meeting_id or event.event_id == meeting_id
        ),
        None,
    )
    transcript_available = record is not None and not is_synthetic_calendar_placeholder(record)
    payload = None
    if transcript_available and record is not None:
        payload = record.model_dump(mode="json")
        payload["transcript"]["segments"] = [
            {**segment, "text": segment["text"][:1_500]}
            for segment in payload["transcript"]["segments"][:40]
        ]
    return {
        "calendar_event": calendar_event.model_dump(mode="json") if calendar_event else None,
        "meeting": payload,
        "transcript_available": transcript_available,
    }


@calendar_mcp.tool()
def search_meetings(
    query: str,
    ctx: Context,
    date_from: str | None = None,
    date_to: str | None = None,
    limit: int = 20,
) -> dict:
    """List and count calendar meetings by arbitrary ISO date range and optional title text."""
    run = _run_context(ctx)
    plan_from = run.plan.date_from if run.plan else None
    plan_to = run.plan.date_to if run.plan else None
    rows = get_store().list_calendar_events(
        run.auth,
        run.request.project_id,
        date_from=plan_from or _tool_datetime(date_from),
        date_to=plan_to or _tool_datetime(date_to),
    )
    rows = [row for row in rows if not row.canceled]
    title_query = query.strip().casefold()
    if title_query:
        title_matches = [
            row
            for row in rows
            if title_query in f"{row.title} {row.description}".casefold()
        ]
        if title_matches:
            rows = title_matches
    bounded_limit = min(max(limit, 1), 50)
    return {
        "count": len(rows),
        "meetings": [row.model_dump(mode="json") for row in rows[:bounded_limit]],
    }


@calendar_mcp.tool()
def search_transcript_chunks(query: str, ctx: Context) -> dict:
    """Semantically search transcript text for a topic, quote, or discussion detail."""
    run = _run_context(ctx)
    rows = get_store().search_transcripts(
        query,
        run.auth,
        run.request.project_id,
        top_k=8,
        meeting_id=run.request.meeting_id,
        date_from=run.plan.date_from if run.plan else None,
        date_to=run.plan.date_to if run.plan else None,
    )
    return {"evidence": _bounded_evidence(rows)}


@calendar_mcp.tool()
def analyze_meeting(meeting_id: str, ctx: Context) -> dict:
    """Generate or reuse structured meeting analysis, then run deterministic anomaly checks."""
    from .meetings import summarize_meeting

    run = _run_context(ctx)
    record = summarize_meeting(get_store(), meeting_id, run.auth)
    if record is None:
        return {"meeting_id": meeting_id, "analysis": None, "transcript_available": False}
    return {
        "meeting_id": meeting_id,
        "title": record.transcript.title,
        "analysis": record.analysis.model_dump(mode="json") if record.analysis else None,
        "analysis_metadata": (
            record.analysis_metadata.model_dump(mode="json")
            if record.analysis_metadata
            else None
        ),
        "transcript_available": True,
    }


@documents_mcp.tool()
def get_document(document_id: str, ctx: Context) -> dict:
    """Get an authorized document by source ID."""
    run = _run_context(ctx)
    rows = get_store().list_knowledge_document_chunks(run.auth, run.request.project_id)
    matches = [row for row in rows if row["source_id"].casefold() == document_id.casefold()]
    return {
        "document": [
            {
                "document_id": row["source_id"],
                "title": row["title"],
                "team": row["team"],
                "source_system": row["source_system"],
                "source_type": row["source_type"],
                "source_uri": row.get("source_uri"),
                "section": row.get("section_path"),
                "content": row["chunk_text"][:1_500],
                "updated_at": (
                    row["source_updated_at"].isoformat()
                    if isinstance(row.get("source_updated_at"), datetime)
                    else row.get("source_updated_at")
                ),
            }
            for row in matches[:12]
        ]
    }


@documents_mcp.tool()
def list_documents(
    query: str,
    ctx: Context,
    team: str | None = None,
    source_type: str | None = None,
    limit: int = 20,
) -> dict:
    """List and count authorized document metadata without embedding retrieval."""
    run = _run_context(ctx)
    chunks = get_store().list_knowledge_document_chunks(run.auth, run.request.project_id)
    documents: dict[str, dict] = {}
    for row in chunks:
        if team and row["team"].casefold() != team.casefold():
            continue
        if source_type and row["source_type"].casefold() != source_type.casefold():
            continue
        entry = documents.setdefault(
            row["source_id"],
            {
                "document_id": row["source_id"],
                "title": row["title"],
                "team": row["team"],
                "source_system": row["source_system"],
                "source_type": row["source_type"],
                "source_uri": row.get("source_uri"),
                "updated_at": (
                    row["source_updated_at"].isoformat()
                    if isinstance(row.get("source_updated_at"), datetime)
                    else row.get("source_updated_at")
                ),
                "sections": [],
            },
        )
        section = row.get("section_path")
        if section and section not in entry["sections"]:
            entry["sections"].append(section)
    rows = list(documents.values())
    normalized_query = query.strip().casefold()
    if normalized_query:
        rows = [
            row
            for row in rows
            if normalized_query
            in (
                f"{row['document_id']} {row['title']} {row['team']} "
                f"{row['source_system']} {row['source_type']}"
            ).casefold()
        ]
    rows.sort(key=lambda row: (row["title"].casefold(), row["document_id"]))
    bounded_limit = min(max(limit, 1), 50)
    return {"count": len(rows), "documents": rows[:bounded_limit]}


@documents_mcp.tool()
def search_documents(query: str, ctx: Context) -> dict:
    """Semantically search authorized document content using the current project scope."""
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
people_mcp_app = people_mcp.streamable_http_app(
    streamable_http_path="/", stateless_http=True, json_response=True, max_sessions=32
)
