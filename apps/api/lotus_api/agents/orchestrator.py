import asyncio
import json
import logging
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from pathlib import Path
from time import perf_counter
from typing import Any
from uuid import uuid4

from google.adk.agents.run_config import RunConfig, StreamingMode
from google.adk.runners import InMemoryRunner
from google.genai import types
from opentelemetry import trace

from ..calendar import is_synthetic_calendar_placeholder
from ..code_store import CodeStore
from ..config import Settings
from ..mcp_servers import register_run_context, release_run_context
from ..models import (
    AgentName,
    Artifact,
    AuthContext,
    ChatMessageRecord,
    ChatRequest,
    Evidence,
    ExecutionPlan,
    GroundedAnswer,
    NavigationTarget,
    Route,
    RouteDecision,
    Scope,
    SpecialistResult,
)
from ..run_events import RunEventSink, bounded_preview, event
from ..storage.base import KnowledgeStore
from ..workspace_context import WorkspaceContextResolver
from .planner import fixture_plan
from .registry import (
    build_documents_agent,
    build_meeting_agent,
    build_planner_agent,
    build_planning_agent,
    build_result_agent,
    build_web_agent,
)

logger = logging.getLogger("uvicorn.error.lotus.orchestration")
tracer = trace.get_tracer("lotus.orchestration")


def _fixture_requires_transcript_search(message: str) -> bool:
    """Offline fallback only; live ADK Meeting Agent selects its own MCP tool."""
    normalized = message.casefold()
    transcript_signals = (
        "what did we discuss",
        "where did we discuss",
        "which meeting",
        "transcript",
        "mentioned",
        "said about",
        "topic",
        "keyword",
        "quote",
    )
    return any(signal in normalized for signal in transcript_signals)


class OrchestrationService:
    """Controlled Planner → specialists → Anomaly → Result execution."""

    def __init__(self, settings: Settings, store: KnowledgeStore):
        self.settings = settings
        self.store = store
        self.code_store = CodeStore(settings.fixture_dir)
        self.workspace_context = WorkspaceContextResolver(store)

    def answer(
        self,
        request: ChatRequest,
        auth: AuthContext,
        emit: RunEventSink | None = None,
        conversation: list[ChatMessageRecord] | None = None,
    ) -> GroundedAnswer:
        execution_id = uuid4().hex[:12]
        started = perf_counter()
        live = self.settings.runtime_mode in {"agent_platform", "vertex"}
        logger.info(
            "orchestration.start execution_id=%s runtime=%s tenant=%s project=%s "
            "meeting_id=%s message_chars=%s",
            execution_id,
            self.settings.runtime_mode,
            auth.tenant_id,
            request.project_id,
            request.meeting_id or "none",
            len(request.message),
        )
        self._emit(
            emit,
            execution_id,
            "run.started",
            session_id=request.session_id,
            output_preview={"runtime": self.settings.runtime_mode},
        )
        try:
            planner_started = perf_counter()
            self._node_started(emit, execution_id, "planner", "Planner", request)
            plan = (
                asyncio.run(self._plan_with_adk(request, conversation or []))
                if live
                else fixture_plan(request)
            )
            self._node_completed(
                emit,
                execution_id,
                "planner",
                "Planner",
                planner_started,
                {"agents": [step.agent.value for step in plan.steps]},
            )
            logger.info(
                "orchestration.plan execution_id=%s agents=%s date_from=%s date_to=%s",
                execution_id,
                ",".join(step.agent.value for step in plan.steps),
                plan.date_from.isoformat() if plan.date_from else "none",
                plan.date_to.isoformat() if plan.date_to else "none",
            )
            specialist_names = [
                step.agent
                for step in plan.steps
                if step.agent
                in {
                    AgentName.DOCUMENTS,
                    AgentName.PLANNING,
                    AgentName.MEETING,
                    AgentName.WEB,
                    AgentName.CODE,
                }
            ]
            with ThreadPoolExecutor(max_workers=max(1, len(specialist_names))) as executor:
                futures = {
                    name: executor.submit(
                        self._run_specialist_logged,
                        execution_id,
                        name,
                        request,
                        auth,
                        plan,
                        emit,
                    )
                    for name in specialist_names
                }
                results = [futures[name].result() for name in specialist_names]

            if any(step.agent is AgentName.ANOMALY for step in plan.steps):
                anomaly_started = perf_counter()
                self._node_started(emit, execution_id, "anomaly", "Anomaly", request)
                anomaly_result = self._run_anomaly(results, auth)
                results.append(anomaly_result)
                self._node_completed(
                    emit,
                    execution_id,
                    "anomaly",
                    "Anomaly",
                    anomaly_started,
                    {"artifacts": len(anomaly_result.artifacts)},
                )
                logger.info(
                    "agent.complete execution_id=%s agent=anomaly evidence=%s artifacts=%s",
                    execution_id,
                    len(anomaly_result.evidence),
                    len(anomaly_result.artifacts),
                )
            result_started = perf_counter()
            self._node_started(emit, execution_id, "result", "Result", request)
            response = self._run_result(request, auth, plan, results, execution_id)
            answer_streamed = False
            cached_input_tokens = 0
            if live:
                response.answer, answer_streamed, cached_input_tokens = asyncio.run(
                    self._run_result_agent(
                        request, response, emit, execution_id, conversation or []
                    )
                )
            self._node_completed(
                emit,
                execution_id,
                "result",
                "Result",
                result_started,
                {
                    "evidence_count": len(response.evidence),
                    "answer_chars": len(response.answer),
                    "cached_input_tokens": cached_input_tokens,
                },
            )
            if not answer_streamed:
                self._stream_answer_deltas(emit, execution_id, request.session_id, response.answer)
            self._emit(
                emit,
                execution_id,
                "answer.completed",
                session_id=request.session_id,
                response=response,
            )
            logger.info(
                "orchestration.complete execution_id=%s agents=%s evidence=%s artifacts=%s "
                "duration_ms=%.1f",
                execution_id,
                ",".join(agent.value for agent in response.agents_used),
                len(response.evidence),
                len(response.artifacts),
                (perf_counter() - started) * 1000,
            )
            return response
        except Exception as exc:
            self._emit(
                emit,
                execution_id,
                "run.failed",
                session_id=request.session_id,
                error=type(exc).__name__,
            )
            logger.exception(
                "orchestration.error execution_id=%s duration_ms=%.1f",
                execution_id,
                (perf_counter() - started) * 1000,
            )
            raise

    @staticmethod
    def _emit(emit: RunEventSink | None, execution_id: str, event_type: str, **values) -> None:
        if emit:
            emit(event(execution_id, event_type, **values))

    def _node_started(
        self,
        emit,
        execution_id,
        node_id,
        label,
        request,
        parent_id=None,
        input_preview=None,
    ):
        preview = input_preview or {
            "project_id": request.project_id,
            "meeting_id": request.meeting_id,
        }
        self._emit(
            emit,
            execution_id,
            "node.started",
            session_id=request.session_id,
            node_id=node_id,
            parent_id=parent_id,
            node_kind="tool" if parent_id else "agent",
            label=label,
            status="running",
            input_preview=bounded_preview(preview),
        )

    @staticmethod
    def _tool_input_preview(request: ChatRequest, plan: ExecutionPlan) -> dict:
        """Expose bounded user-controlled tool arguments without agent/system prompts."""
        return {
            "query": request.message,
            "project_id": request.project_id,
            "meeting_id": request.meeting_id,
            "repository_id": request.repository_id,
            "planning_item_ids": request.planning_item_ids,
            "document_ids": request.document_ids,
            "date_from": plan.date_from.isoformat() if plan.date_from else None,
            "date_to": plan.date_to.isoformat() if plan.date_to else None,
        }

    def _node_completed(self, emit, execution_id, node_id, label, started, output, parent_id=None):
        self._emit(
            emit,
            execution_id,
            "node.completed",
            node_id=node_id,
            parent_id=parent_id,
            node_kind="tool" if parent_id else "agent",
            label=label,
            status="completed",
            duration_ms=round((perf_counter() - started) * 1000, 1),
            output_preview=bounded_preview(output),
        )

    def _stream_answer_deltas(self, emit, execution_id, session_id, answer):
        if not emit:
            return
        chunks = answer.split(" ")
        for index, chunk in enumerate(chunks):
            self._emit(
                emit,
                execution_id,
                "answer.delta",
                session_id=session_id,
                answer_delta=("" if index == 0 else " ") + chunk,
            )

    async def _run_agent_details(
        self, agent, user_id: str, prompt: str, on_delta=None, timeout_seconds=None
    ) -> tuple[str, Any | None, int]:
        started = perf_counter()
        timeout_seconds = timeout_seconds or self.settings.agent_timeout_seconds
        logger.info("adk.start agent=%s prompt_chars=%s", agent.name, len(prompt))
        runner = InMemoryRunner(
            agent=agent,
            app_name="lotus",
        )
        session = await runner.session_service.create_session(app_name="lotus", user_id=user_id)
        final_text = ""
        grounding_metadata = None
        cached_input_tokens = 0
        try:
            async with asyncio.timeout(timeout_seconds):
                async for event in runner.run_async(
                    user_id=user_id,
                    session_id=session.id,
                    new_message=types.Content(role="user", parts=[types.Part(text=prompt)]),
                    run_config=(RunConfig(streaming_mode=StreamingMode.SSE) if on_delta else None),
                ):
                    usage = getattr(event, "usage_metadata", None)
                    cached_input_tokens = max(
                        cached_input_tokens,
                        int(getattr(usage, "cached_content_token_count", 0) or 0),
                    )
                    if event.grounding_metadata:
                        grounding_metadata = event.grounding_metadata
                    if event.is_final_response() and event.content:
                        final_text = "".join(part.text or "" for part in event.content.parts)
                    elif on_delta and event.partial and event.content:
                        delta = "".join(part.text or "" for part in event.content.parts)
                        if delta:
                            on_delta(delta)
        except TimeoutError:
            logger.warning(
                "adk.timeout agent=%s timeout_seconds=%.1f",
                agent.name,
                timeout_seconds,
            )
            raise
        logger.info(
            "adk.complete agent=%s output_chars=%s grounded=%s "
            "cached_input_tokens=%s duration_ms=%.1f",
            agent.name,
            len(final_text),
            grounding_metadata is not None,
            cached_input_tokens,
            (perf_counter() - started) * 1000,
        )
        current_span = trace.get_current_span()
        if current_span.is_recording():
            current_span.set_attribute("gen_ai.usage.cached_input_tokens", cached_input_tokens)
        return final_text, grounding_metadata, cached_input_tokens

    async def _run_agent(self, agent, user_id: str, prompt: str) -> str:
        output, _, _ = await self._run_agent_details(agent, user_id, prompt)
        return output

    @staticmethod
    def _conversation_text(conversation: list[ChatMessageRecord]) -> str:
        return "\n".join(f"{row.role}: {row.content}" for row in conversation)

    async def _plan_with_adk(
        self, request: ChatRequest, conversation: list[ChatMessageRecord] | None = None
    ) -> ExecutionPlan:
        prompt = (
            f"Current UTC time: {datetime.now(UTC).isoformat()}\n"
            f"Project: {request.project_id}\n"
            f"Meeting context: {request.meeting_id or 'none'}\n"
            f"Recent conversation:\n{self._conversation_text(conversation or []) or 'none'}\n"
            f"User request: {request.message}"
        )
        try:
            output = await self._run_agent(build_planner_agent(self.settings), "planner", prompt)
        except TimeoutError:
            logger.warning("planner.fallback reason=timeout route=result")
            return ExecutionPlan(
                steps=[
                    {
                        "agent": AgentName.RESULT,
                        "intent": "Respond safely because the Planner timed out.",
                        "depends_on": [],
                    }
                ],
                reason=(
                    "The Planner timed out. Route directly to Result for a safe degraded "
                    "response without retrieving unrelated enterprise data."
                ),
            )
        plan = self._validate_live_plan(output)
        return plan

    def _validate_live_plan(self, output: str) -> ExecutionPlan:
        plan = ExecutionPlan.model_validate_json(output)
        allowed = {
            AgentName.DOCUMENTS,
            AgentName.PLANNING,
            AgentName.MEETING,
            AgentName.WEB,
            AgentName.CODE,
        }
        specialists = [step for step in plan.steps if step.agent in allowed]
        anomaly = [step for step in plan.steps if step.agent is AgentName.ANOMALY]
        if anomaly and not any(step.agent is AgentName.MEETING for step in specialists):
            raise ValueError("Anomaly agent requires meeting evidence")
        result_steps = [step for step in plan.steps if step.agent is AgentName.RESULT]
        if len(result_steps) != 1 or plan.steps[-1].agent is not AgentName.RESULT:
            raise ValueError("Agent Platform planner must schedule Result last")
        if not specialists and len(plan.steps) != 1:
            raise ValueError("A plan without specialists must contain only Result")
        return plan

    async def _run_result_agent(
        self,
        request: ChatRequest,
        grounded: GroundedAnswer,
        emit: RunEventSink | None = None,
        execution_id: str = "",
        conversation: list[ChatMessageRecord] | None = None,
    ) -> tuple[str, bool, int]:
        prompt = (
            "Validated Lotus response contract follows.\n"
            f"Recent conversation:\n{self._conversation_text(conversation or []) or 'none'}\n"
            f"User request: {request.message}\n"
            f"Validated execution plan and authorized evidence: {grounded.model_dump_json()}"
        )
        streamed = False

        def on_delta(delta: str) -> None:
            nonlocal streamed
            streamed = True
            self._emit(
                emit,
                execution_id,
                "answer.delta",
                session_id=request.session_id,
                answer_delta=delta,
            )

        try:
            output, _, cached_input_tokens = await self._run_agent_details(
                build_result_agent(self.settings), "result", prompt, on_delta
            )
        except TimeoutError:
            logger.warning("result.fallback reason=timeout")
            return grounded.answer, streamed, 0
        return output or grounded.answer, streamed, cached_input_tokens

    def _run_specialist(self, name, request, auth, plan) -> SpecialistResult:
        live = self.settings.runtime_mode in {"agent_platform", "vertex"}
        if live and name in {AgentName.DOCUMENTS, AgentName.PLANNING, AgentName.MEETING}:
            try:
                return asyncio.run(self._live_mcp_specialist(name, request, auth, plan))
            except Exception as exc:
                logger.warning(
                    "specialist.fallback agent=%s reason=%s", name.value, type(exc).__name__
                )
        if name is AgentName.DOCUMENTS:
            selected = self.workspace_context.resolve(request, auth)
            retrieved = self.store.search_documents(
                request.message, auth, request.project_id, self.settings.max_evidence_items
            )
            evidence = list({row.source_id: row for row in [*selected, *retrieved]}.values())[
                : self.settings.max_evidence_items
            ]
            artifacts = []
            if "diagram" in request.message.casefold() or "flow" in request.message.casefold():
                artifacts.append(
                    Artifact(
                        artifact_type="mermaid",
                        title="Generated architecture flow",
                        content=(
                            "flowchart LR\n  User --> Planner\n  Planner --> Documents\n"
                            "  Planner --> Meeting\n  Documents --> Result\n  Meeting --> Result"
                        ),
                    )
                )
            return SpecialistResult(agent=name, evidence=evidence, artifacts=artifacts)
        if name is AgentName.PLANNING:
            project = self.store.get_workspace_project(request.project_id, auth)
            evidence: list[Evidence] = []
            if project:
                stakeholder_text = "; ".join(
                    f"{row.employee.name} — {row.role}, {row.employee.designation}, "
                    f"{row.employee.email} ({row.employee.contact_handle})"
                    for row in project.stakeholders
                )
                evidence.append(
                    Evidence(
                        source_id=project.project_id,
                        source_system="lotus_planner",
                        source_type="project",
                        title=project.name,
                        snippet=(
                            f"{project.description} Status: {project.status}. "
                            f"Stakeholders: {stakeholder_text}"
                        ),
                        retrieval_method="planner_repository",
                        scope=Scope(
                            tenant_id=auth.tenant_id, project_id=request.project_id
                        ),
                        navigation_target=NavigationTarget(
                            kind="project",
                            entity_id=project.project_id,
                            project_id=project.project_id,
                            label=f"Open {project.name}",
                        ),
                    )
                )
            issues = self.store.list_board_issues(auth, request.project_id)
            message = request.message.casefold()
            for issue in issues:
                if issue.issue_key.casefold() in message:
                    evidence.append(
                        Evidence(
                            source_id=issue.issue_key,
                            source_system="lotus_planner",
                            source_type="planning_item",
                            title=issue.title,
                            snippet=(
                                f"{issue.issue_key}: {issue.title}. Status {issue.status}; "
                                f"priority {issue.priority}; assignee {issue.assignee_id}."
                            ),
                            retrieval_method="planner_repository",
                            scope=Scope(
                                tenant_id=auth.tenant_id, project_id=request.project_id
                            ),
                            navigation_target=NavigationTarget(
                                kind="planning_item",
                                entity_id=issue.issue_key,
                                project_id=issue.project_id,
                                label=f"Open {issue.issue_key}",
                            ),
                        )
                    )
            return SpecialistResult(agent=name, evidence=evidence)
        if name is AgentName.MEETING:
            if not _fixture_requires_transcript_search(request.message):
                return SpecialistResult(
                    agent=name,
                    evidence=self._calendar_meeting_evidence(request, auth, plan),
                )
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
        if name is AgentName.CODE:
            return SpecialistResult(
                agent=name,
                evidence=self.code_store.search(
                    request.message,
                    auth,
                    request.project_id,
                    request.repository_id,
                    self.settings.max_evidence_items,
                ),
            )
        if self.settings.runtime_mode in {"agent_platform", "vertex"}:
            evidence = asyncio.run(self._live_web(request, auth))
        else:
            evidence = self._fixture_web(request, auth)
        return SpecialistResult(agent=name, evidence=evidence)

    def _run_specialist_logged(
        self,
        execution_id: str,
        name: AgentName,
        request: ChatRequest,
        auth: AuthContext,
        plan: ExecutionPlan,
        emit: RunEventSink | None = None,
    ) -> SpecialistResult:
        started = perf_counter()
        self._node_started(emit, execution_id, name.value, name.value.title(), request)
        tool = {
            AgentName.DOCUMENTS: "documents_mcp",
            AgentName.PLANNING: "planner_mcp",
            AgentName.MEETING: "calendar_mcp",
            AgentName.WEB: "web_search",
            AgentName.CODE: "repository_search",
        }[name]
        tool_started = perf_counter()
        self._node_started(
            emit,
            execution_id,
            f"{name.value}.{tool}",
            tool,
            request,
            name.value,
            self._tool_input_preview(request, plan),
        )
        logger.info("agent.start execution_id=%s agent=%s", execution_id, name.value)
        try:
            with tracer.start_as_current_span(f"lotus.agent.{name.value}") as span:
                span.set_attribute("lotus.execution_id", execution_id)
                span.set_attribute("lotus.session_id", request.session_id or "none")
                span.set_attribute("lotus.agent", name.value)
                result = self._run_specialist(name, request, auth, plan)
                span.set_attribute("lotus.evidence_count", len(result.evidence))
        except Exception as exc:
            for node_id, label, parent_id in (
                (f"{name.value}.{tool}", tool, name.value),
                (name.value, name.value.title(), None),
            ):
                self._emit(
                    emit,
                    execution_id,
                    "node.failed",
                    node_id=node_id,
                    parent_id=parent_id,
                    node_kind="tool" if parent_id else "agent",
                    label=label,
                    status="failed",
                    duration_ms=round((perf_counter() - started) * 1000, 1),
                    error=type(exc).__name__,
                )
            raise
        self._node_completed(
            emit,
            execution_id,
            f"{name.value}.{tool}",
            tool,
            tool_started,
            {"evidence_count": len(result.evidence), "artifact_count": len(result.artifacts)},
            name.value,
        )
        self._node_completed(
            emit,
            execution_id,
            name.value,
            name.value.title(),
            started,
            {"evidence_count": len(result.evidence), "artifact_count": len(result.artifacts)},
        )
        logger.info(
            "agent.complete execution_id=%s agent=%s evidence=%s artifacts=%s duration_ms=%.1f",
            execution_id,
            name.value,
            len(result.evidence),
            len(result.artifacts),
            (perf_counter() - started) * 1000,
        )
        return result

    async def _live_mcp_specialist(
        self,
        name: AgentName,
        request: ChatRequest,
        auth: AuthContext,
        plan: ExecutionPlan,
    ) -> SpecialistResult:
        context_id, headers = register_run_context(auth, request, plan)
        try:
            builder = {
                AgentName.DOCUMENTS: build_documents_agent,
                AgentName.PLANNING: build_planning_agent,
                AgentName.MEETING: build_meeting_agent,
            }[name]
            prompt = (
                f"Project: {request.project_id}\n"
                f"Meeting ID: {request.meeting_id or 'none'}\n"
                f"Selected planning items: {request.planning_item_ids}\n"
                f"Selected documents: {request.document_ids}\n"
                f"Trusted planner date range: {plan.date_from or 'none'} to "
                f"{plan.date_to or 'none'}\n"
                f"Current UTC time: {datetime.now(UTC).isoformat()}\n"
                f"Request: {request.message}"
            )
            output = await self._run_agent(builder(self.settings, headers), auth.user_id, prompt)
            result = SpecialistResult.model_validate_json(output)
            if result.agent is not name:
                raise ValueError("Specialist returned the wrong agent identity")
            return result
        finally:
            release_run_context(context_id)

    def _calendar_meeting_evidence(
        self,
        request: ChatRequest,
        auth: AuthContext,
        plan: ExecutionPlan,
    ) -> list[Evidence]:
        if request.meeting_id:
            meeting_ids = [request.meeting_id]
        else:
            meetings = self.store.list_calendar_events(
                auth,
                request.project_id,
                date_from=plan.date_from,
                date_to=plan.date_to,
            )
            limit = 1 if any(
                signal in request.message.casefold()
                for signal in ("last meeting", "latest meeting", "most recent meeting")
            ) else self.settings.max_evidence_items
            meeting_ids = [row.meeting_id for row in meetings if not row.canceled][:limit]

        evidence: list[Evidence] = []
        for meeting_id in meeting_ids:
            record = self.store.get_meeting(meeting_id, auth)
            event = next(
                (
                    row
                    for row in self.store.list_calendar_events(auth, request.project_id)
                    if row.meeting_id == meeting_id
                ),
                None,
            )
            if event is None:
                continue
            details = [
                f"{event.title} was scheduled from {event.started_at.isoformat()} "
                f"to {event.ended_at.isoformat()}.",
                f"Organizer: {event.organizer}.",
                f"Details: {event.description}",
            ]
            if (
                record
                and not is_synthetic_calendar_placeholder(record)
                and record.analysis
                and record.analysis.summary
            ):
                details.append(f"Summary: {record.analysis.summary}")
            evidence.append(
                Evidence(
                    source_id=meeting_id,
                    source_system="calendar",
                    source_type="meeting_record",
                    title=event.title,
                    uri=f"lotus://meetings/{meeting_id}",
                    snippet=" ".join(details)[:1_500],
                    updated_at=event.started_at.isoformat(),
                    retrieval_method="calendar_lookup",
                    scope=Scope(
                        tenant_id=auth.tenant_id,
                        project_id=request.project_id,
                        meeting_id=meeting_id,
                    ),
                    meeting_id=meeting_id,
                    navigation_target=NavigationTarget(
                        kind="meeting",
                        entity_id=meeting_id,
                        project_id=request.project_id,
                        label=f"Open {event.title}",
                    ),
                )
            )
        return evidence

    async def _live_web(self, request: ChatRequest, auth: AuthContext) -> list[Evidence]:
        try:
            output, grounding, _ = await self._run_agent_details(
                build_web_agent(self.settings),
                auth.user_id,
                request.message,
                timeout_seconds=self.settings.web_agent_timeout_seconds,
            )
        except TimeoutError:
            logger.warning("web.fallback reason=timeout")
            return []
        if not output:
            return []
        chunks = list(grounding.grounding_chunks or []) if grounding else []
        supports = list(grounding.grounding_supports or []) if grounding else []
        evidence: list[Evidence] = []
        for index, chunk in enumerate(chunks):
            if not chunk.web or not chunk.web.uri:
                continue
            excerpts = [
                support.segment.text
                for support in supports
                if support.segment
                and support.segment.text
                and index in (support.grounding_chunk_indices or [])
            ]
            evidence.append(
                Evidence(
                    source_id=chunk.web.uri,
                    source_system="web",
                    source_type="google_search_grounding",
                    title=chunk.web.title or chunk.web.domain,
                    uri=chunk.web.uri,
                    snippet=" ".join(dict.fromkeys(excerpts)) or output,
                    retrieval_method="agent_platform_google_search",
                    scope=Scope(
                        tenant_id=auth.tenant_id,
                        project_id=request.project_id,
                    ),
                )
            )
        if evidence:
            return evidence[: self.settings.max_evidence_items]
        return [
            Evidence(
                source_id="agent-platform-google-search",
                source_system="web",
                source_type="google_search_grounding",
                title="Google Search grounded research",
                snippet=output,
                retrieval_method="agent_platform_google_search",
                scope=Scope(
                    tenant_id=auth.tenant_id,
                    project_id=request.project_id,
                ),
            )
        ]

    def _fixture_web(self, request: ChatRequest, auth: AuthContext) -> list[Evidence]:
        payload = json.loads(
            (Path(self.settings.fixture_dir) / "web/results.json").read_text(encoding="utf-8")
        )
        words = set(request.message.casefold().split())
        ranked = sorted(
            payload,
            key=lambda row: (
                -len(words & set(f"{row['title']} {row['snippet']}".casefold().split()))
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

    def _run_anomaly(self, results: list[SpecialistResult], auth: AuthContext) -> SpecialistResult:
        artifacts: list[Artifact] = []
        meeting_ids = {
            row.meeting_id for result in results for row in result.evidence if row.meeting_id
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

    def _run_result(self, request, auth, plan, results, execution_id) -> GroundedAnswer:
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
        if plan.artifact_request == "mermaid" and not any(
            artifact.artifact_type == "mermaid" for artifact in artifacts
        ):
            lowered = " ".join([request.message, *(row.snippet for row in evidence)]).casefold()
            if "retry" in lowered or "checkout" in lowered:
                diagram = (
                    "flowchart LR\n"
                    "  Customer --> CheckoutClient[Checkout client]\n"
                    "  CheckoutClient --> Gateway[Payment gateway]\n"
                    "  Gateway --> Provider[Payment provider]\n"
                    "  Provider -->|retryable failure| Backoff[Exponential backoff]\n"
                    "  Backoff -->|full jitter; max 3 attempts| Gateway\n"
                    "  Gateway --> Ledger[Idempotency ledger]"
                )
            else:
                diagram = (
                    "flowchart LR\n"
                    "  User --> Planner\n"
                    "  Planner --> Documents[Documents Agent]\n"
                    "  Documents --> Sources[Authorized sources]\n"
                    "  Sources --> Result[Result Agent]\n"
                    "  Result --> Diagram[Grounded diagram]"
                )
            artifacts.append(
                Artifact(
                    artifact_type="mermaid",
                    title="Architecture flow",
                    content=diagram,
                )
            )
        scope = Scope(
            tenant_id=auth.tenant_id,
            project_id=request.project_id,
            meeting_id=request.meeting_id,
            repository_id=request.repository_id,
        )
        direct_result = len(plan.steps) == 1 and plan.steps[0].agent is AgentName.RESULT
        if direct_result:
            answer = "Lotus is ready to help."
            uncertainty = []
        elif evidence:
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
        elif AgentName.CODE in used:
            route = Route.CODE
        else:
            route = Route.KNOWLEDGE
        return GroundedAnswer(
            execution_id=execution_id,
            answer=answer,
            evidence=evidence,
            scope=scope,
            uncertainty=uncertainty,
            next_action="Open a cited item to inspect its provenance." if evidence else None,
            route=RouteDecision(
                route=route,
                confidence=1.0,
                reason="Planner-selected agent path.",
                live_retrieval=(
                    self.settings.runtime_mode in {"agent_platform", "vertex"}
                    and AgentName.WEB in used
                ),
            ),
            agents_used=used,
            plan=plan,
            artifacts=artifacts,
            navigation_targets=list(
                {
                    (target.kind, target.entity_id): target
                    for target in (row.navigation_target for row in evidence)
                    if target is not None
                }.values()
            ),
            session_id=request.session_id,
        )
