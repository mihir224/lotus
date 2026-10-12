import re

from .models import ChatRequest, Mode, Route, RouteDecision

JIRA_KEY = re.compile(r"\b[A-Z][A-Z0-9]+-\d+\b")
CONFLUENCE_PAGE = re.compile(r"(?:page(?:\s+id)?\s*[:#]?\s*)(\d{4,})", re.IGNORECASE)


MODE_ROUTES = {
    Mode.ASK_COMPANY: Route.KNOWLEDGE,
    Mode.MEETING: Route.MEETING,
    Mode.CODE: Route.CODE,
    Mode.DOCUMENT: Route.DOCUMENT,
    Mode.RESEARCH: Route.RESEARCH,
}


def route_request(request: ChatRequest) -> RouteDecision:
    if request.mode is not Mode.AUTO:
        return RouteDecision(
            route=MODE_ROUTES[request.mode],
            confidence=1.0,
            reason="User selected an explicit mode.",
            live_retrieval=request.mode is Mode.DOCUMENT,
        )

    message = request.message
    lowered = message.casefold()
    if request.meeting_id or "this meeting" in lowered:
        return RouteDecision(
            route=Route.MEETING,
            confidence=0.99,
            reason="Meeting scope is explicit.",
        )
    code_signals = ("patch", "code change", "run tests")
    if request.repository_id or any(word in lowered for word in code_signals):
        return RouteDecision(
            route=Route.CODE,
            confidence=0.9,
            reason="A repository action was requested.",
        )
    if CONFLUENCE_PAGE.search(message) or "confluence" in lowered:
        return RouteDecision(
            route=Route.DOCUMENT,
            confidence=0.96,
            reason="An exact Confluence source was requested.",
            live_retrieval=True,
        )
    if JIRA_KEY.search(message):
        return RouteDecision(
            route=Route.KNOWLEDGE,
            confidence=0.99,
            reason="A Jira issue key requires exact source retrieval.",
            live_retrieval=True,
        )
    if any(word in lowered for word in ("latest public", "web research", "search the web")):
        return RouteDecision(
            route=Route.RESEARCH,
            confidence=0.88,
            reason="The request explicitly asks for current public information.",
            live_retrieval=True,
        )
    return RouteDecision(
        route=Route.KNOWLEDGE,
        confidence=0.8,
        reason="The request is an internal knowledge question.",
    )
