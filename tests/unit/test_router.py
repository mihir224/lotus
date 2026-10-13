from lotus_api.agents.planner import fixture_plan
from lotus_api.models import AgentName, ChatRequest, Route
from lotus_api.router import route_request


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


def test_planner_combines_data_meeting_and_anomaly() -> None:
    plan = fixture_plan(request("Compare the architecture with meeting action item gaps"))
    assert [step.agent for step in plan.steps] == [
        AgentName.DATA,
        AgentName.MEETING,
        AgentName.ANOMALY,
        AgentName.RESULT,
    ]
