from datetime import datetime
from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Route(StrEnum):
    KNOWLEDGE = "knowledge"
    MEETING = "meeting"
    CODE = "code"
    DOCUMENT = "document"
    RESEARCH = "research"


class AgentName(StrEnum):
    DATA = "data"
    MEETING = "meeting"
    WEB = "web"
    ANOMALY = "anomaly"
    CODE = "code"
    RESULT = "result"


class AuthContext(StrictModel):
    tenant_id: str
    user_id: str
    principals: tuple[str, ...]
    email: str | None = None
    name: str | None = None


class AuthConfig(StrictModel):
    mode: Literal["dev", "google"]
    google_client_id: str | None = None


class AuthenticatedUser(StrictModel):
    user_id: str
    email: str | None = None
    name: str | None = None


class ChatRequest(StrictModel):
    message: str = Field(min_length=1, max_length=8_000)
    project_id: str = Field(min_length=1, max_length=128)
    meeting_id: str | None = None
    repository_id: str | None = None
    session_id: str | None = Field(default=None, max_length=128)
    planning_item_ids: list[str] = Field(default_factory=list, max_length=20)
    document_ids: list[str] = Field(default_factory=list, max_length=20)


class Scope(StrictModel):
    tenant_id: str
    project_id: str | None = None
    meeting_id: str | None = None
    repository_id: str | None = None


class Evidence(StrictModel):
    source_id: str
    source_system: str
    source_type: str
    title: str | None = None
    uri: str | None = None
    snippet: str
    section: str | None = None
    updated_at: str | None = None
    retrieval_method: str
    scope: Scope
    score: float | None = None
    version: str | None = None
    meeting_id: str | None = None
    start_ms: int | None = None
    end_ms: int | None = None


class RouteDecision(StrictModel):
    route: Route
    confidence: float = Field(ge=0, le=1)
    reason: str
    live_retrieval: bool = False


class PlanStep(StrictModel):
    agent: AgentName
    intent: str
    depends_on: list[AgentName] = Field(default_factory=list)


class ExecutionPlan(StrictModel):
    steps: list[PlanStep]
    reason: str
    date_from: datetime | None = None
    date_to: datetime | None = None


class Artifact(StrictModel):
    artifact_type: Literal["mermaid", "meeting_analysis"]
    title: str
    content: str | dict[str, Any]


class SpecialistResult(StrictModel):
    agent: AgentName
    evidence: list[Evidence] = Field(default_factory=list)
    artifacts: list[Artifact] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class GroundedAnswer(StrictModel):
    execution_id: str
    answer: str
    evidence: list[Evidence]
    scope: Scope
    uncertainty: list[str] = Field(default_factory=list)
    next_action: str | None = None
    route: RouteDecision
    agents_used: list[AgentName] = Field(default_factory=list)
    plan: ExecutionPlan | None = None
    artifacts: list[Artifact] = Field(default_factory=list)


class TranscriptSegment(StrictModel):
    segment_id: str
    start_ms: int = Field(ge=0)
    end_ms: int = Field(ge=0)
    speaker: str
    text: str = Field(min_length=1)


class MeetingTranscriptInput(StrictModel):
    calendar_event_id: str
    title: str
    project_id: str
    team: str
    started_at: datetime
    ended_at: datetime
    participants: list[str]
    language_code: str = "en"
    recording_url: str | None = None
    segments: list[TranscriptSegment] = Field(min_length=1)


class Decision(StrictModel):
    text: str
    timestamp_ms: int | None = None
    evidence_segment_ids: list[str] = Field(default_factory=list)


class ActionItem(StrictModel):
    text: str
    owner: str | None = None
    due_date: str | None = None
    timestamp_ms: int | None = None
    evidence_segment_ids: list[str] = Field(default_factory=list)


class Anomaly(StrictModel):
    anomaly_type: Literal[
        "unowned_action",
        "missing_due_date",
        "unresolved_question",
        "document_conflict",
    ]
    severity: Literal["low", "medium", "high"]
    description: str
    evidence_segment_ids: list[str] = Field(default_factory=list)


class MeetingAnalysis(StrictModel):
    summary: str
    decisions: list[Decision] = Field(default_factory=list)
    action_items: list[ActionItem] = Field(default_factory=list)
    open_questions: list[str] = Field(default_factory=list)
    anomalies: list[Anomaly] = Field(default_factory=list)


class MeetingAnalysisMetadata(StrictModel):
    method: Literal["fixture", "agent_platform", "fallback"]
    model: str
    input_hash: str
    generated_at: datetime


class MeetingRecord(StrictModel):
    meeting_id: str
    tenant_id: str
    transcript: MeetingTranscriptInput
    analysis: MeetingAnalysis | None = None
    analysis_metadata: MeetingAnalysisMetadata | None = None
    status: Literal["received", "processed", "failed"] = "received"
    updated_at: datetime


class MeetingListItem(StrictModel):
    meeting_id: str
    calendar_event_id: str
    title: str
    project_id: str
    team: str
    started_at: datetime
    ended_at: datetime
    language_code: str
    status: str


class CalendarEventItem(StrictModel):
    event_id: str
    meeting_id: str
    project_id: str
    title: str
    organizer: str
    organizer_initials: str
    location: str | None = None
    description: str
    started_at: datetime
    ended_at: datetime
    canceled: bool = False
    recurring: bool = False


class RunEvent(StrictModel):
    event_type: Literal[
        "run.started",
        "node.started",
        "node.completed",
        "node.failed",
        "answer.delta",
        "answer.completed",
        "run.failed",
        "heartbeat",
    ]
    execution_id: str
    session_id: str | None = None
    timestamp: datetime = Field(default_factory=lambda: datetime.now().astimezone())
    node_id: str | None = None
    parent_id: str | None = None
    node_kind: Literal["agent", "tool"] | None = None
    label: str | None = None
    status: Literal["pending", "running", "completed", "failed"] | None = None
    duration_ms: float | None = None
    input_preview: dict[str, Any] | None = None
    output_preview: dict[str, Any] | None = None
    answer_delta: str | None = None
    response: GroundedAnswer | None = None
    error: str | None = None
