from datetime import UTC, datetime, timedelta

from ..models import AgentName, ChatRequest, ExecutionPlan, PlanStep


def previous_week(now: datetime) -> tuple[datetime, datetime]:
    local = now.astimezone(UTC)
    current_monday = (local - timedelta(days=local.weekday())).replace(
        hour=0, minute=0, second=0, microsecond=0
    )
    return current_monday - timedelta(days=7), current_monday


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
    data_signals = (
        "document",
        "documentation",
        "architecture",
        "runbook",
        "product",
        "jira",
        "confluence",
        "sharepoint",
        "github",
        "similar work",
        "diagram",
    )
    steps: list[PlanStep] = []
    if any(signal in message for signal in data_signals):
        steps.append(PlanStep(agent=AgentName.DATA, intent=request.message))
    if request.meeting_id or any(signal in message for signal in meeting_signals):
        steps.append(PlanStep(agent=AgentName.MEETING, intent=request.message))
    elif " call " in f" {message} ":
        steps.append(PlanStep(agent=AgentName.MEETING, intent=request.message))
    if any(signal in message for signal in web_signals):
        steps.append(PlanStep(agent=AgentName.WEB, intent=request.message))
    if not steps:
        steps.append(PlanStep(agent=AgentName.DATA, intent=request.message))

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
    if "last week" in message:
        date_from, date_to = previous_week(now)
    return ExecutionPlan(
        steps=steps,
        reason="Planner selected agents from the request and available scope.",
        date_from=date_from,
        date_to=date_to,
    )
