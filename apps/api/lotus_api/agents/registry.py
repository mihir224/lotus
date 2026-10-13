from dataclasses import dataclass

from google.adk.agents import Agent
from google.adk.tools import google_search

from ..config import Settings
from ..models import AuthContext, ChatRequest
from ..storage.base import KnowledgeStore


@dataclass(frozen=True)
class AgentContext:
    request: ChatRequest
    auth: AuthContext
    store: KnowledgeStore


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

    data = Agent(
        name="data_agent",
        model=settings.generation_model,
        instruction="Search company sources using only the supplied tool and return evidence.",
        tools=[search_company_documents],
    )
    meeting = Agent(
        name="meeting_agent",
        model=settings.generation_model,
        instruction="Search transcript evidence, preserving meeting IDs and timestamps.",
        tools=[search_meeting_transcripts],
    )
    anomaly = Agent(
        name="anomaly_agent",
        model=settings.generation_model,
        instruction="Review meeting evidence for explicit gaps and contradictions only.",
    )
    web = Agent(
        name="web_search_agent",
        model=settings.generation_model,
        instruction="Use Google Search for public-web evidence and cite sources.",
        tools=[google_search],
    )
    result = Agent(
        name="result_agent",
        model=settings.generation_model,
        instruction="Compose the final answer exclusively from normalized evidence and artifacts.",
    )
    return Agent(
        name="lotus_planner",
        model=settings.router_model,
        instruction=(
            "Create a plan, then transfer among the necessary specialists. Never ask the user "
            "to choose a mode. Always transfer to result_agent last."
        ),
        sub_agents=[data, meeting, anomaly, web, result],
    )
