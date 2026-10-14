from dataclasses import dataclass

from google import genai
from google.adk.agents import Agent
from google.adk.models.google_llm import Gemini
from google.adk.tools import google_search

from ..config import Settings
from ..models import AuthContext, ChatRequest, ExecutionPlan
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
            "You are the Lotus Planner. Select one or more specialists from data, meeting, and "
            "web. Use data for internal documents and similar-team work; meeting for calendar, "
            "transcript, decision, action-item, and historical-meeting questions; web only for "
            "public internet research. For greetings, thanks, test messages, help, and questions "
            "about Lotus capabilities, select result as the only step; do not invoke a specialist. "
            "Independent specialists have no dependencies. Add anomaly after meeting only when "
            "the request asks for gaps, conflicts, anomalies, action items, or open questions. "
            "Always add result as the final step depending on every prior step. For relative "
            "dates, populate explicit UTC date_from/date_to bounds."
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
            "Preserve bracketed citation numbers, state uncertainty when evidence is insufficient, "
            "and never claim that a source or meeting said something absent from the evidence."
        ),
    )


def build_web_agent(settings: Settings) -> Agent:
    return Agent(
        name="web_search_agent",
        model=_model(settings, settings.generation_model),
        timeout=settings.agent_timeout_seconds,
        instruction=(
            "Research the user's question on the public web using Google Search. Return a concise "
            "evidence brief with source titles and URLs. Distinguish sourced facts from inference."
        ),
        tools=[google_search],
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
    data = Agent(
        name="data_agent",
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
        sub_agents=[data, meeting, anomaly, web, result],
    )
