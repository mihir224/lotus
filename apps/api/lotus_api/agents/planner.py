import re
from datetime import UTC, datetime, timedelta

from ..models import AgentName, ChatRequest, ExecutionPlan, PlanStep


def previous_week(now: datetime) -> tuple[datetime, datetime]:
    local = now.astimezone(UTC)
    current_monday = (local - timedelta(days=local.weekday())).replace(
        hour=0, minute=0, second=0, microsecond=0
    )
    return current_monday - timedelta(days=7), current_monday


_MONTHS = {
    name: number
    for number, names in enumerate(
        (
            (),
            ("jan", "january"),
            ("feb", "february"),
            ("mar", "march"),
            ("apr", "april"),
            ("may",),
            ("jun", "june"),
            ("jul", "july"),
            ("aug", "august"),
            ("sep", "sept", "september"),
            ("oct", "october"),
            ("nov", "november"),
            ("dec", "december"),
        )
    )
    for name in names
}


def explicit_day(message: str, now: datetime) -> tuple[datetime, datetime] | None:
    """Resolve common day/month forms for the deterministic offline planner."""
    normalized = message.casefold()
    patterns = (
        r"\b(\d{1,2})(?:st|nd|rd|th)?\s+([a-z]+)(?:\s+(\d{4}))?\b",
        r"\b([a-z]+)\s+(\d{1,2})(?:st|nd|rd|th)?(?:,?\s+(\d{4}))?\b",
    )
    for index, pattern in enumerate(patterns):
        match = re.search(pattern, normalized)
        if not match:
            continue
        day_text, month_text, year_text = (
            match.groups() if index == 0 else (match.group(2), match.group(1), match.group(3))
        )
        month = _MONTHS.get(month_text)
        if month is None:
            continue
        try:
            start = datetime(int(year_text or now.year), month, int(day_text), tzinfo=UTC)
        except ValueError:
            return None
        return start, start + timedelta(days=1)
    return None


def fixture_plan(request: ChatRequest, now: datetime | None = None) -> ExecutionPlan:
    """Deterministic offline implementation of the Planner Agent contract."""
    message = request.message.casefold()
    now = now or datetime.now(UTC)
    meeting_signals = (
        "meeting",
        "transcript",
        "discuss",
        "last week",
        "action item",
        "open question",
    )
    web_signals = ("web", "public", "internet", "current guidance", "research")
    code_signals = (
        "source code",
        "codebase",
        "repository",
        "repo",
        "implementation",
        "function",
        "source file",
    )
    document_signals = (
        "document",
        "documentation",
        "architecture",
        "runbook",
        "product",
        "confluence",
        "sharepoint",
        "github",
        "similar work",
        "diagram",
    )
    planning_signals = (
        "jira",
        "project",
        "planner",
        "ticket",
        "issue",
        "stakeholder",
        "owner",
        "contact",
        "who works",
    )
    steps: list[PlanStep] = []
    if any(signal in message for signal in document_signals):
        steps.append(PlanStep(agent=AgentName.DOCUMENTS, intent=request.message))
    if request.planning_item_ids or any(signal in message for signal in planning_signals):
        steps.append(PlanStep(agent=AgentName.PLANNING, intent=request.message))
    if request.meeting_id or any(signal in message for signal in meeting_signals):
        steps.append(PlanStep(agent=AgentName.MEETING, intent=request.message))
    elif " call " in f" {message} ":
        steps.append(PlanStep(agent=AgentName.MEETING, intent=request.message))
    if any(signal in message for signal in web_signals):
        steps.append(PlanStep(agent=AgentName.WEB, intent=request.message))
    if request.repository_id or any(signal in message for signal in code_signals):
        steps.append(PlanStep(agent=AgentName.CODE, intent=request.message))
    if not steps:
        conversational = (
            "hello",
            "hi ",
            "hey",
            "thanks",
            "thank you",
            "who are you",
            "what can you do",
            "wie heisst du",
            "wie heißt du",
            "namaste",
        )
        if any(signal in f"{message} " for signal in conversational):
            steps.append(PlanStep(agent=AgentName.RESULT, intent=request.message))
            return ExecutionPlan(
                steps=steps,
                reason="No enterprise retrieval was needed; Result can answer conversationally.",
            )
        steps.append(PlanStep(agent=AgentName.DOCUMENTS, intent=request.message))

    anomaly_requested = any(
        signal in message for signal in ("anomaly", "open question", "action item", "gap")
    )
    if anomaly_requested and any(step.agent is AgentName.MEETING for step in steps):
        steps.append(
            PlanStep(
                agent=AgentName.ANOMALY,
                intent="Analyze meeting-content gaps after meeting retrieval.",
                depends_on=[AgentName.MEETING],
            )
        )
    steps.append(
        PlanStep(
            agent=AgentName.RESULT,
            intent="Compose the final grounded response.",
            depends_on=[step.agent for step in steps],
        )
    )
    date_from = date_to = None
    explicit_range = explicit_day(message, now)
    if explicit_range:
        date_from, date_to = explicit_range
    elif "last week" in message:
        date_from, date_to = previous_week(now)
    return ExecutionPlan(
        steps=steps,
        reason="Planner selected agents from the request and available scope.",
        date_from=date_from,
        date_to=date_to,
        artifact_request=(
            "mermaid"
            if "diagram" in message or "flowchart" in message or "architecture flow" in message
            else None
        ),
    )
