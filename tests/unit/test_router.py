from lotus_api.models import ChatRequest, Mode, Route
from lotus_api.router import route_request


def request(message: str, **kwargs: object) -> ChatRequest:
    return ChatRequest(message=message, project_id="payments", **kwargs)


def test_routes_jira_key_to_live_knowledge() -> None:
    result = route_request(request("What is the current status of PAY-123?"))
    assert result.route is Route.KNOWLEDGE
    assert result.live_retrieval is True


def test_explicit_mode_wins() -> None:
    result = route_request(request("PAY-123", mode=Mode.RESEARCH))
    assert result.route is Route.RESEARCH


def test_meeting_scope_is_hard_signal() -> None:
    result = route_request(request("What did we decide?", meeting_id="M-104"))
    assert result.route is Route.MEETING
