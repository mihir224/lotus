from typing import Literal

from google import genai
from google.adk.agents import Agent
from google.adk.models.google_llm import Gemini
from google.adk.tools import google_search
from google.adk.tools.mcp_tool import McpToolset, StreamableHTTPConnectionParams

from ..config import Settings
from ..models import ExecutionPlan, MeetingAnalysis, SpecialistResult


def _model(settings: Settings, model_id: str) -> Gemini:
    client = genai.Client(
        enterprise=True,
        project=settings.google_cloud_project,
        location=settings.google_cloud_location,
    )
    return Gemini(model=model_id, client=client)


def build_planner_agent(settings: Settings) -> Agent:
    return Agent(
        name="lotus_planner",
        model=_model(settings, settings.router_model),
        timeout=settings.agent_timeout_seconds,
        instruction=(
            "You are the Lotus Planner. Select one or more specialists from documents, planning, "
            "people, meeting, web, and code. Use documents for internal knowledge, architecture, "
            "and similar-team work; planning for projects and work items; people for employee "
            "profiles, contacts, stakeholders, teams, and subject-matter experts; meeting "
            "for calendar, "
            "transcript, decision, action-item, and historical-meeting questions; web only for "
            "public internet research; code for repository implementation questions. For "
            "greetings, "
            "thanks, test messages, help, and questions "
            "about Lotus capabilities, select result as the only step; do not invoke a specialist. "
            "Meeting handles summaries, action items, questions, and anomaly requests itself; "
            "never add a separate analysis or anomaly agent. Independent specialists have no "
            "dependencies. Always add result as the final step depending on every prior step. "
            "For relative "
            "dates—including arbitrary days, months, and relative dates—populate explicit UTC "
            "date_from/date_to bounds. Set artifact_request to "
            "mermaid only when the user explicitly requests an architecture or process diagram."
        ),
        output_schema=ExecutionPlan,
        output_key="execution_plan",
    )


def build_result_agent(settings: Settings) -> Agent:
    return Agent(
        name="result_agent",
        model=_model(settings, settings.generation_model),
        timeout=settings.agent_timeout_seconds,
        instruction=(
            "Inspect the validated execution plan. When result is its only step, respond naturally "
            "to greetings, thanks, test messages, help, or questions about Lotus capabilities; do "
            "not invent company facts. You are Iris, the AI assistant inside the Lotus workspace; "
            "if a result-only plan contains an enterprise factual "
            "request, explain that routing was unavailable and ask the user to retry. When any "
            "specialist is present, answer only from supplied normalized evidence and artifacts. "
            "Treat calendar-only records as schedule metadata, not proof that a meeting occurred. "
            "Never call a calendar description a transcript or invent discussion content when "
            "transcript_available is false. Present meeting dates and times naturally instead of "
            "dumping ISO timestamps, use the display timezone supplied in the response prompt, "
            "and omit internal meeting IDs unless the user asks for them. "
            "Preserve bracketed citation numbers, state uncertainty when evidence is insufficient, "
            "and never claim that a source or meeting said something absent from the evidence."
        ),
    )


def build_web_agent(settings: Settings) -> Agent:
    return Agent(
        name="web_search_agent",
        model=_model(settings, settings.generation_model),
        timeout=settings.web_agent_timeout_seconds,
        instruction=(
            "Research the user's question on the public web using Google Search. Return a concise "
            "evidence brief with source titles and URLs. Distinguish sourced facts from inference. "
            "When the request asks for official or first-party guidance, search and cite only the "
            "organization's own domains; do not use blogs, aggregators, or vendor summaries."
        ),
        tools=[google_search],
    )


def _mcp_toolset(settings: Settings, path: str, headers: dict[str, str]) -> McpToolset:
    return McpToolset(
        connection_params=StreamableHTTPConnectionParams(
            url=f"{settings.internal_mcp_base_url}{path}/",
            headers=headers,
            timeout=10,
            sse_read_timeout=settings.agent_timeout_seconds,
        ),
        tool_list_cache_ttl_seconds=60,
    )


def build_documents_agent(settings: Settings, headers: dict[str, str]) -> Agent:
    return Agent(
        name="documents_agent",
        model=_model(settings, settings.generation_model),
        timeout=settings.agent_timeout_seconds,
        instruction=(
            "Use only the Documents MCP tools and infer the user's document intent yourself. "
            "Use list_documents for counts, inventories, teams, source types, and document "
            "metadata. Use get_document for an explicit document ID or a selected document. Use "
            "search_documents only when the question requires semantic retrieval from document "
            "content. Never run vector search merely to count or list documents. Return a "
            "SpecialistResult with agent='documents', preserving source IDs and structured "
            "document navigation. Do not compose the final answer."
        ),
        tools=[_mcp_toolset(settings, "/internal/mcp/documents", headers)],
        output_schema=SpecialistResult,
        output_key="documents_result",
    )


def build_planning_agent(settings: Settings, headers: dict[str, str]) -> Agent:
    return Agent(
        name="planning_agent",
        model=_model(settings, settings.generation_model),
        timeout=settings.agent_timeout_seconds,
        instruction=(
            "Use only the Planner MCP tools and infer the user's planning intent yourself. Use "
            "get_project for project metadata, get_planning_item for an explicit issue key, and "
            "search_planning_items for counts, "
            "lists, text queries, status, team, assignee, or priority filters. Planning queries "
            "are structured database lookups and never vector searches. Return a SpecialistResult "
            "with agent='planning' and structured project or planning-item navigation. Do not "
            "compose the final answer."
        ),
        tools=[_mcp_toolset(settings, "/internal/mcp/planner", headers)],
        output_schema=SpecialistResult,
        output_key="planning_result",
    )


def build_people_agent(settings: Settings, headers: dict[str, str]) -> Agent:
    return Agent(
        name="people_agent",
        model=_model(settings, settings.generation_model),
        timeout=settings.agent_timeout_seconds,
        instruction=(
            "Use only the Employee Directory MCP tools. Use get_employee for an explicit person, "
            "search_employees for name, team, designation, timezone, or directory queries, "
            "get_employee_project_stakeholders for project contacts, and "
            "find_subject_matter_experts for expertise requests. Expertise is a structured-data "
            "match, not a guarantee; preserve the returned basis. Return a SpecialistResult with "
            "agent='people' and employee_directory evidence. Do not compose the final answer."
        ),
        tools=[_mcp_toolset(settings, "/internal/mcp/people", headers)],
        output_schema=SpecialistResult,
        output_key="people_result",
    )


def build_meeting_agent(
    settings: Settings,
    headers: dict[str, str] | None = None,
    task: Literal["retrieve", "summarize"] = "retrieve",
) -> Agent:
    if task == "summarize":
        return Agent(
            name="meeting_agent",
            model=_model(settings, settings.generation_model),
            timeout=settings.agent_timeout_seconds,
            instruction=(
                "Analyze only the supplied timestamped transcript. Produce a concise summary, "
                "decisions, action items, and unresolved questions. Every decision and action "
                "must cite valid segment IDs and timestamps from the input. Do not infer owners "
                "or dates. Leave anomalies and clarifications empty because deterministic tools "
                "run after extraction."
            ),
            output_schema=MeetingAnalysis,
            output_key="meeting_analysis",
        )
    if headers is None:
        raise ValueError("Meeting retrieval requires scoped MCP headers")
    return Agent(
        name="meeting_agent",
        model=_model(settings, settings.generation_model),
        timeout=settings.agent_timeout_seconds,
        instruction=(
            "Use only the Calendar MCP tools to retrieve authorized meeting evidence. Infer the "
            "user's calendar intent and choose tools yourself. Use search_meetings for counts, "
            "lists, arbitrary date ranges, recency, titles, and meeting metadata; it returns both "
            "a count and records. Use get_meeting when full details for a selected meeting are "
            "needed. Use search_transcript_chunks only to locate a topic, keyword, quote, or "
            "discussion inside transcripts. Never use transcript embeddings merely to count or "
            "list calendar meetings. A get_meeting response with transcript_available=false is "
            "calendar metadata only; do not present its title or description as transcript "
            "content. Use analyze_meeting when the user asks for a summary, decisions, action "
            "items, open questions, clarifications, conflicts, or anomalies. "
            "Return a SpecialistResult with agent='meeting'. Use "
            "retrieval_method='calendar_lookup' for calendar/get_meeting records and preserve "
            "meeting navigation targets. Preserve returned structured analysis as a "
            "meeting_analysis artifact. Do not compose the final answer."
        ),
        tools=[_mcp_toolset(settings, "/internal/mcp/calendar", headers)],
        output_schema=SpecialistResult,
        output_key="meeting_result",
    )
