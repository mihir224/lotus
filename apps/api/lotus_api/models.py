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
    RESULT = "result"


class AuthContext(StrictModel):
    tenant_id: str
    user_id: str
    principals: tuple[str, ...]
    email: str | None = None
    name: str | None = None
    designation: str | None = None
    picture_url: str | None = None


class AuthConfig(StrictModel):
    mode: Literal["dev", "google"]
    google_client_id: str | None = None


class AuthenticatedUser(StrictModel):
    user_id: str
    email: str | None = None
    name: str | None = None
    designation: str | None = None
    picture_url: str | None = None


class ChatRequest(StrictModel):
    message: str = Field(min_length=1, max_length=8_000)
    project_id: str = Field(min_length=1, max_length=128)
    meeting_id: str | None = None
    repository_id: str | None = None


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


class MeetingRecord(StrictModel):
    meeting_id: str
    tenant_id: str
    transcript: MeetingTranscriptInput
    analysis: MeetingAnalysis | None = None
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


class CalendarEventCreate(StrictModel):
    title: str = Field(min_length=1, max_length=200)
    project_id: str = Field(default="payments", min_length=1, max_length=128)
    location: str | None = None
    description: str = ""
    started_at: datetime
    ended_at: datetime
    attendees: list[str] = Field(default_factory=list)
    video_meeting: bool = False


BoardIssueStatus = Literal[
    "ready_to_start",
    "development",
    "review",
    "testing",
    "done",
]
BoardIssueType = Literal["bug", "user_story"]
BoardIssuePriority = Literal["low", "medium", "high"]


class BoardAssignee(StrictModel):
    assignee_id: str
    name: str
    initials: str
    avatar_color: str = "#2563eb"


class BoardTeam(StrictModel):
    team_id: str
    name: str
    key_prefix: str


class BoardMeta(StrictModel):
    project_id: str
    project_name: str
    board_title: str


class BoardIssueItem(StrictModel):
    issue_key: str
    project_id: str
    team_id: str
    title: str
    issue_type: BoardIssueType
    feature_key: str
    feature_title: str
    description: str = ""
    acceptance_criteria: list[str] = Field(default_factory=list)
    priority: BoardIssuePriority = "medium"
    story_points: int = Field(default=0, ge=0, le=99)
    sprint: str | None = None
    reporter_id: str
    status: BoardIssueStatus
    assignee_id: str


class BoardIssueUpdate(StrictModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    issue_type: BoardIssueType | None = None
    status: BoardIssueStatus | None = None
    assignee_id: str | None = None
    description: str | None = None
    acceptance_criteria: list[str] | None = None
    priority: BoardIssuePriority | None = None
    story_points: int | None = Field(default=None, ge=0, le=99)
    reporter_id: str | None = None


BOARD_ISSUE_UNASSIGNED = "unassigned"


class BoardIssueCreate(StrictModel):
    title: str = Field(min_length=1, max_length=200)
    project_id: str
    team_id: str
    feature_key: str = Field(min_length=1, max_length=32)
    issue_type: BoardIssueType = "user_story"
    status: BoardIssueStatus = "ready_to_start"
    assignee_id: str = BOARD_ISSUE_UNASSIGNED
    reporter_id: str = BOARD_ISSUE_UNASSIGNED
    description: str = ""
    acceptance_criteria: list[str] = Field(default_factory=list)
    priority: BoardIssuePriority = "medium"
    story_points: int = Field(default=0, ge=0, le=99)


class WorkBoardResponse(StrictModel):
    board: BoardMeta
    teams: list[BoardTeam]
    assignees: list[BoardAssignee]
    issues: list[BoardIssueItem]


DocSourceType = Literal[
    "architecture",
    "runbook",
    "product",
    "adr",
    "policy",
    "issue",
    "product_doc",
    "release_note",
    "guide",
]


class DocSourceSummary(StrictModel):
    source_id: str
    title: str
    team: str
    source_type: str
    source_system: str
    updated_at: str | None = None


class DocTeamGroup(StrictModel):
    team: str
    pages: list[DocSourceSummary]


class DocCatalogResponse(StrictModel):
    project_id: str
    groups: list[DocTeamGroup]


class DocPageDetail(StrictModel):
    source_id: str
    project_id: str
    title: str
    team: str
    source_type: str
    source_system: str
    source_uri: str | None = None
    body: str
    updated_at: str | None = None


class DocSearchHit(StrictModel):
    source_id: str
    title: str
    team: str
    source_type: str
    snippet: str
    updated_at: str | None = None


class DocSourceCreate(StrictModel):
    project_id: str = Field(min_length=1, max_length=128)
    title: str = Field(min_length=1, max_length=240)
    team: str = Field(min_length=1, max_length=120)
    source_type: DocSourceType = "guide"
    body: str = Field(min_length=1, max_length=50_000)
