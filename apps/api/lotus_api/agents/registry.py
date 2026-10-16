from dataclasses import dataclass

from google import genai
from google.adk.agents import Agent
from google.adk.models.google_llm import Gemini
from google.adk.tools import google_search
from google.adk.tools.mcp_tool import McpToolset, StreamableHTTPConnectionParams

from ..config import Settings
from ..models import (
    AuthContext,
    ChatRequest,
    ExecutionPlan,
    MeetingAnalysis,
    SpecialistResult,
)
from ..storage.base import KnowledgeStore


@dataclass(frozen=True)
class AgentContext:
    request: ChatRequest
    auth: AuthContext
    store: KnowledgeStore


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
            "meeting, web, and code. Use documents for internal knowledge, architecture, and "
            "similar-team work; planning for projects, work items, and stakeholders; meeting "
            "for calendar, "
            "transcript, decision, action-item, and historical-meeting questions; web only for "
            "public internet research; code for repository implementation questions. For "
            "greetings, "
            "thanks, test messages, help, and questions "
            "about Lotus capabilities, select result as the only step; do not invoke a specialist. "
            "Independent specialists have no dependencies. Add anomaly after meeting only when "
            "the request asks for gaps, conflicts, anomalies, action items, or open questions. "
            "Always add result as the final step depending on every prior step. For relative "
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
            "not invent company facts. If a result-only plan contains an enterprise factual "
            "request, explain that routing was unavailable and ask the user to retry. When any "
            "specialist is present, answer only from supplied normalized evidence and artifacts. "
            "Treat calendar-only records as schedule metadata, not proof that a meeting occurred. "
            "Never call a calendar description a transcript or invent discussion content when "
            "transcript_available is false. Present meeting dates and times naturally instead of "
            "dumping ISO timestamps, and omit internal meeting IDs unless the user asks for them. "
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
            "evidence brief with source titles and URLs. Distinguish sourced facts from inference."
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
            "get_project for project metadata, get_project_stakeholders for owners and contacts, "
            "get_planning_item for an explicit issue key, and search_planning_items for counts, "
            "lists, text queries, status, team, assignee, or priority filters. Planning queries "
            "are structured database lookups and never vector searches. Return a SpecialistResult "
            "with agent='planning' and structured project or planning-item navigation. Do not "
            "compose the final answer."
        ),
        tools=[_mcp_toolset(settings, "/internal/mcp/planner", headers)],
        output_schema=SpecialistResult,
        output_key="planning_result",
    )


def build_meeting_agent(settings: Settings, headers: dict[str, str]) -> Agent:
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
            "content. "
            "Return a SpecialistResult with agent='meeting'. Use "
            "retrieval_method='calendar_lookup' for calendar/get_meeting records and preserve "
            "meeting navigation targets. Do not compose the final answer."
        ),
        tools=[_mcp_toolset(settings, "/internal/mcp/calendar", headers)],
        output_schema=SpecialistResult,
        output_key="meeting_result",
    )


def build_meeting_analysis_agent(settings: Settings) -> Agent:
    return Agent(
        name="meeting_analysis_agent",
        model=_model(settings, settings.generation_model),
        timeout=settings.agent_timeout_seconds,
        instruction=(
            "Analyze only the supplied timestamped transcript. Produce a concise summary, "
            "decisions, action items, and unresolved questions. Every decision must cite valid "
            "segment IDs and timestamps from the input. Do not infer owners or dates. Leave "
            "anomalies empty because deterministic policy checks run after extraction."
        ),
        output_schema=MeetingAnalysis,
        output_key="meeting_analysis",
    )


def build_agent_tree(settings: Settings, context: AgentContext) -> Agent:
    """Build the ADK agent graph. Authorization stays in captured server context."""

    def search_company_documents(query: str) -> dict:
        """Search authorized enterprise document chunks."""
        rows = context.store.search_documents(query, context.auth, context.request.project_id)
        return {"evidence": [row.model_dump(mode="json") for row in rows]}

    def search_meeting_transcripts(query: str) -> dict:
        """Search authorized timestamped meeting transcript chunks."""
        rows = context.store.search_transcripts(
            query,
            context.auth,
            context.request.project_id,
            meeting_id=context.request.meeting_id,
        )
        return {"evidence": [row.model_dump(mode="json") for row in rows]}

    generation_model = _model(settings, settings.generation_model)
    router_model = _model(settings, settings.router_model)
    documents = Agent(
        name="documents_agent",
        model=generation_model,
        timeout=settings.agent_timeout_seconds,
        instruction="Search company sources using only the supplied tool and return evidence.",
        tools=[search_company_documents],
    )
    meeting = Agent(
        name="meeting_agent",
        model=generation_model,
        timeout=settings.agent_timeout_seconds,
        instruction="Search transcript evidence, preserving meeting IDs and timestamps.",
        tools=[search_meeting_transcripts],
    )
    anomaly = Agent(
        name="anomaly_agent",
        model=generation_model,
        timeout=settings.agent_timeout_seconds,
        instruction="Review meeting evidence for explicit gaps and contradictions only.",
    )
    web = Agent(
        name="web_search_agent",
        model=generation_model,
        timeout=settings.agent_timeout_seconds,
        instruction="Use Google Search for public-web evidence and cite sources.",
        tools=[google_search],
    )
    result = Agent(
        name="result_agent",
        model=generation_model,
        timeout=settings.agent_timeout_seconds,
        instruction="Compose the final answer exclusively from normalized evidence and artifacts.",
    )
    return Agent(
        name="lotus_planner",
        model=router_model,
        timeout=settings.agent_timeout_seconds,
        instruction=(
            "Create a plan, then transfer among the necessary specialists. Never ask the user "
            "to choose a mode. Always transfer to result_agent last."
        ),
        sub_agents=[documents, meeting, anomaly, web, result],
    )
