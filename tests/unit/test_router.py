import asyncio
import json
from datetime import UTC, datetime
from unittest.mock import AsyncMock

from lotus_api.agents.orchestrator import OrchestrationService
from lotus_api.agents.planner import fixture_plan
from lotus_api.config import Settings
from lotus_api.embeddings import DeterministicEmbedder
from lotus_api.models import AgentName, ChatRequest, Route
from lotus_api.router import route_request
from lotus_api.storage.memory import MemoryKnowledgeStore


def request(message: str, **kwargs: object) -> ChatRequest:
    return ChatRequest(message=message, project_id="payments", **kwargs)


def test_routes_jira_key_to_live_knowledge() -> None:
    result = route_request(request("What is the current status of PAY-123?"))
    assert result.route is Route.KNOWLEDGE
    assert result.live_retrieval is False


def test_planner_selects_web_without_a_user_mode() -> None:
    plan = fixture_plan(request("Search the web for current guidance"))
    assert [step.agent for step in plan.steps] == [AgentName.WEB, AgentName.RESULT]


def test_meeting_scope_is_hard_signal() -> None:
    result = route_request(request("What did we decide?", meeting_id="M-104"))
    assert result.route is Route.MEETING


def test_planner_keeps_meeting_analysis_inside_meeting_agent() -> None:
    plan = fixture_plan(request("Compare the architecture with meeting action item gaps"))
    assert [step.agent for step in plan.steps] == [
        AgentName.DOCUMENTS,
        AgentName.MEETING,
        AgentName.RESULT,
    ]


def test_planner_routes_employee_contacts_to_people() -> None:
    plan = fixture_plan(request("Who are the stakeholders I can contact?"))
    assert [step.agent for step in plan.steps] == [AgentName.PEOPLE, AgentName.RESULT]


def test_live_plan_accepts_direct_result_for_conversation() -> None:
    settings = Settings(runtime_mode="fixture", store_backend="memory")
    store = MemoryKnowledgeStore(settings, DeterministicEmbedder())
    service = OrchestrationService(settings, store)

    plan = service._validate_live_plan(
        json.dumps(
            {
                "steps": [
                    {
                        "agent": "result",
                        "intent": "Respond to the greeting.",
                        "depends_on": [],
                    }
                ],
                "reason": "This is a conversational greeting.",
                "date_from": None,
                "date_to": None,
            }
        )
    )

    assert [step.agent for step in plan.steps] == [AgentName.RESULT]


def test_live_planner_timeout_falls_back_to_result_without_data() -> None:
    settings = Settings(runtime_mode="agent_platform", store_backend="memory")
    store = MemoryKnowledgeStore(settings, DeterministicEmbedder())
    service = OrchestrationService(settings, store)
    service._run_agent = AsyncMock(side_effect=TimeoutError)

    plan = asyncio.run(service._plan_with_adk(request("wie heisst du?")))

    assert [step.agent for step in plan.steps] == [AgentName.RESULT]
    assert "timed out" in plan.reason


def test_planner_routes_project_stakeholders_to_people() -> None:
    plan = fixture_plan(request("Who are the stakeholders for the payments project?"))
    assert [step.agent for step in plan.steps] == [AgentName.PEOPLE, AgentName.RESULT]


def test_fixture_planner_resolves_arbitrary_calendar_days() -> None:
    plan = fixture_plan(
        request("How many meetings did I have on 15th Aug?"),
        now=datetime(2026, 10, 16, tzinfo=UTC),
    )
    assert plan.date_from == datetime(2026, 8, 15, tzinfo=UTC)
    assert plan.date_to == datetime(2026, 8, 16, tzinfo=UTC)

    reversed_date = fixture_plan(
        request("What meetings did I have on February 14, 2025?"),
        now=datetime(2026, 10, 16, tzinfo=UTC),
    )
    assert reversed_date.date_from == datetime(2025, 2, 14, tzinfo=UTC)
    assert reversed_date.date_to == datetime(2025, 2, 15, tzinfo=UTC)
