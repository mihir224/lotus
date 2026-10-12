from .models import AuthContext, ChatRequest, GroundedAnswer, Route, Scope
from .retrieval import exact_jira, semantic_search, unique_sources
from .router import route_request


def answer_chat(request: ChatRequest, auth: AuthContext) -> GroundedAnswer:
    decision = route_request(request)
    scope = Scope(
        tenant_id=auth.tenant_id,
        project_id=request.project_id,
        meeting_id=request.meeting_id,
        repository_id=request.repository_id,
    )

    if decision.route is not Route.KNOWLEDGE:
        return GroundedAnswer(
            answer=f"The {decision.route.value} specialist is scaffolded but not implemented yet.",
            evidence=[],
            scope=scope,
            uncertainty=["This route is outside the first fixture-backed knowledge slice."],
            next_action="Use Ask company mode while the next hero flow is being implemented.",
            route=decision,
        )

    exact = exact_jira(request, auth)
    semantic = semantic_search(request, auth)
    evidence = unique_sources([*exact, *semantic])
    if not evidence:
        return GroundedAnswer(
            answer=(
                "I could not verify this in the permitted product, technical, Jira, "
                "or Confluence fixture sources."
            ),
            evidence=[],
            scope=scope,
            uncertainty=["No authorized evidence matched the question."],
            next_action="Try a more specific term or confirm the selected project.",
            route=decision,
        )

    citations = " ".join(f"[{index}]" for index in range(1, len(evidence) + 1))
    summaries = " ".join(item.snippet for item in evidence[:3])
    return GroundedAnswer(
        answer=f"{summaries} {citations}",
        evidence=evidence,
        scope=scope,
        uncertainty=[
            "Fixture-backed lexical retrieval is active; Gemini synthesis is not enabled."
        ],
        next_action="Open an evidence item to inspect its source and provenance.",
        route=decision,
    )
