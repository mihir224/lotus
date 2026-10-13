"""Compatibility helpers for callers migrating to planner-led routing."""

from .agents.planner import fixture_plan
from .models import AgentName, ChatRequest, Route, RouteDecision


def route_request(request: ChatRequest) -> RouteDecision:
    agents = [step.agent for step in fixture_plan(request).steps]
    if AgentName.MEETING in agents:
        route = Route.MEETING
    elif AgentName.WEB in agents:
        route = Route.RESEARCH
    else:
        route = Route.KNOWLEDGE
    return RouteDecision(
        route=route,
        confidence=1.0,
        reason="Derived from the Planner Agent execution plan.",
        live_retrieval=False,
    )
