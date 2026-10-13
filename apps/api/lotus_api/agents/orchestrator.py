import asyncio
import json
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from google.adk.runners import InMemoryRunner
from google.genai import types

from ..config import Settings
from ..models import (
    AgentName,
    Artifact,
    AuthContext,
    ChatRequest,
    Evidence,
    GroundedAnswer,
    Route,
    RouteDecision,
    Scope,
    SpecialistResult,
)
from ..storage.base import KnowledgeStore
from .planner import fixture_plan
from .registry import AgentContext, build_agent_tree


class OrchestrationService:
    """Controlled Planner → specialists → Anomaly → Result execution."""

    def __init__(self, settings: Settings, store: KnowledgeStore):
        self.settings = settings
        self.store = store

    def answer(self, request: ChatRequest, auth: AuthContext) -> GroundedAnswer:
        plan = fixture_plan(request)
        specialist_names = [
            step.agent
            for step in plan.steps
            if step.agent in {AgentName.DATA, AgentName.MEETING, AgentName.WEB}
        ]
        with ThreadPoolExecutor(max_workers=max(1, len(specialist_names))) as executor:
            futures = {
                name: executor.submit(self._run_specialist, name, request, auth, plan)
                for name in specialist_names
            }
            results = [futures[name].result() for name in specialist_names]

        if any(step.agent is AgentName.ANOMALY for step in plan.steps):
            results.append(self._run_anomaly(results, auth))
        response = self._run_result(request, auth, plan, results)
        if self.settings.runtime_mode == "vertex":
            response.answer = asyncio.run(self._run_adk(request, auth, response))
        return response

    async def _run_adk(
        self, request: ChatRequest, auth: AuthContext, grounded: GroundedAnswer
    ) -> str:
        """Run the live Google ADK graph; server-side evidence remains the trust boundary."""
        context = AgentContext(request=request, auth=auth, store=self.store)
        runner = InMemoryRunner(
            agent=build_agent_tree(self.settings, context),
            app_name="lotus",
        )
        session = await runner.session_service.create_session(
            app_name="lotus", user_id=auth.user_id
        )
        prompt = (
            f"User request: {request.message}\n"
            f"Server plan and authorized evidence: {grounded.model_dump_json()}\n"
            "Follow the plan, call only necessary specialists, and have result_agent answer last."
        )
        final_text = ""
        async for event in runner.run_async(
            user_id=auth.user_id,
            session_id=session.id,
            new_message=types.Content(role="user", parts=[types.Part(text=prompt)]),
        ):
            if event.is_final_response() and event.content:
                final_text = "".join(part.text or "" for part in event.content.parts)
        return final_text or grounded.answer

    def _run_specialist(self, name, request, auth, plan) -> SpecialistResult:
        if name is AgentName.DATA:
            evidence = self.store.search_documents(
                request.message, auth, request.project_id, self.settings.max_evidence_items
            )
            artifacts = []
            if "diagram" in request.message.casefold() or "flow" in request.message.casefold():
                artifacts.append(
                    Artifact(
                        artifact_type="mermaid",
                        title="Generated architecture flow",
                        content=(
                            "flowchart LR\n  User --> Planner\n  Planner --> Data\n"
                            "  Planner --> Meeting\n  Data --> Result\n  Meeting --> Result"
                        ),
                    )
                )
            return SpecialistResult(agent=name, evidence=evidence, artifacts=artifacts)
        if name is AgentName.MEETING:
            return SpecialistResult(
                agent=name,
                evidence=self.store.search_transcripts(
                    request.message,
                    auth,
                    request.project_id,
                    self.settings.max_evidence_items,
                    request.meeting_id,
                    plan.date_from,
                    plan.date_to,
                ),
            )
        return SpecialistResult(agent=name, evidence=self._fixture_web(request, auth))

    def _fixture_web(self, request: ChatRequest, auth: AuthContext) -> list[Evidence]:
        payload = json.loads(
            (Path(self.settings.fixture_dir) / "web/results.json").read_text(encoding="utf-8")
        )
        words = set(request.message.casefold().split())
        ranked = sorted(
            payload,
            key=lambda row: -len(
                words & set(f"{row['title']} {row['snippet']}".casefold().split())
            ),
        )
        return [
            Evidence(
                source_id=row["source_id"],
                source_system="web",
                source_type="web_page",
                title=row["title"],
                uri=row["uri"],
                snippet=row["snippet"],
                retrieval_method="web_fixture",
                scope=Scope(tenant_id=auth.tenant_id, project_id=request.project_id),
            )
            for row in ranked[:3]
        ]

    def _run_anomaly(
        self, results: list[SpecialistResult], auth: AuthContext
    ) -> SpecialistResult:
        artifacts: list[Artifact] = []
        meeting_ids = {
            row.meeting_id
            for result in results
            for row in result.evidence
            if row.meeting_id
        }
        for meeting_id in sorted(meeting_ids):
            record = self.store.get_meeting(meeting_id, auth)
            if record and record.analysis:
                artifacts.append(
                    Artifact(
                        artifact_type="meeting_analysis",
                        title=f"Analysis: {record.transcript.title}",
                        content=record.analysis.model_dump(mode="json"),
                    )
                )
        return SpecialistResult(agent=AgentName.ANOMALY, artifacts=artifacts)

    def _run_result(self, request, auth, plan, results) -> GroundedAnswer:
        evidence: list[Evidence] = []
        artifacts: list[Artifact] = []
        seen: set[tuple[str, str]] = set()
        for result in results:
            artifacts.extend(result.artifacts)
            for row in result.evidence:
                key = (row.source_system, row.source_id)
                if key not in seen:
                    evidence.append(row)
                    seen.add(key)
        evidence = evidence[: self.settings.max_evidence_items]
        scope = Scope(
            tenant_id=auth.tenant_id,
            project_id=request.project_id,
            meeting_id=request.meeting_id,
            repository_id=request.repository_id,
        )
        if evidence:
            answer = " ".join(row.snippet for row in evidence[:3])
            answer += " " + " ".join(f"[{index}]" for index in range(1, len(evidence) + 1))
            uncertainty = ["Fixture runtime composed this answer from deterministic retrieval."]
        else:
            answer = "I could not verify this in the authorized sources."
            uncertainty = ["No authorized evidence matched the question."]
        used = [step.agent for step in plan.steps]
        if AgentName.MEETING in used:
            route = Route.MEETING
        elif AgentName.WEB in used:
            route = Route.RESEARCH
        else:
            route = Route.KNOWLEDGE
        return GroundedAnswer(
            answer=answer,
            evidence=evidence,
            scope=scope,
            uncertainty=uncertainty,
            next_action="Open a cited item to inspect its provenance." if evidence else None,
            route=RouteDecision(
                route=route,
                confidence=1.0,
                reason="Planner-selected agent path.",
                live_retrieval=self.settings.runtime_mode == "vertex" and AgentName.WEB in used,
            ),
            agents_used=used,
            plan=plan,
            artifacts=artifacts,
        )
