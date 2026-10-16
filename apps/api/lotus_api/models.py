from datetime import datetime
from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Route(StrEnum):
    KNOWLEDGE = "knowledge"
    MEETING = "meeting"
    CODE = "code"
    DOCUMENT = "document"
    RESEARCH = "research"


class AgentName(StrEnum):
    DOCUMENTS = "documents"
    PLANNING = "planning"
    PEOPLE = "people"
    MEETING = "meeting"
    WEB = "web"
    CODE = "code"
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
    session_id: str | None = Field(default=None, max_length=128)
    planning_item_ids: list[str] = Field(default_factory=list, max_length=20)
    document_ids: list[str] = Field(default_factory=list, max_length=20)


class NavigationTarget(StrictModel):
    kind: Literal["meeting", "document", "project", "planning_item"]
    entity_id: str
    project_id: str | None = None
    label: str
    timestamp_ms: int | None = Field(default=None, ge=0)


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
    navigation_target: NavigationTarget | None = None


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
    artifact_request: Literal["mermaid"] | None = None


class Artifact(StrictModel):
    artifact_type: Literal["mermaid", "meeting_analysis"]
    title: str
    content: str | dict[str, Any]
    navigation_target: NavigationTarget | None = None

    @model_validator(mode="after")
    def validate_mermaid(self):
        if self.artifact_type != "mermaid":
            return self
        if not isinstance(self.content, str):
            raise ValueError("Mermaid artifact content must be text")
        if len(self.content) > 12_000:
            raise ValueError("Mermaid artifact exceeds the size limit")
        first = self.content.lstrip().splitlines()[0] if self.content.strip() else ""
        if not first.startswith(("flowchart ", "sequenceDiagram", "stateDiagram")):
            raise ValueError("Unsupported Mermaid diagram type")
        return self


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
    navigation_targets: list[NavigationTarget] = Field(default_factory=list)
    session_id: str | None = None


class ChatSessionCreate(StrictModel):
    project_id: str = Field(default="payments", min_length=1, max_length=128)


class ChatSessionSummary(StrictModel):
    session_id: str
    title: str
    project_id: str
    created_at: datetime
    updated_at: datetime


class ChatSessionPage(StrictModel):
    items: list[ChatSessionSummary]
    next_cursor: str | None = None


class ChatMessageRecord(StrictModel):
    message_id: str
    session_id: str
    role: Literal["user", "assistant"]
    content: str
    execution_id: str | None = None
    status: Literal["running", "completed", "failed"]
    response: GroundedAnswer | None = None
    created_at: datetime


class ChatSessionDetail(StrictModel):
    session: ChatSessionSummary
    messages: list[ChatMessageRecord]


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


class ClarificationNeeded(StrictModel):
    kind: Literal["open_question", "anomaly", "decision_conflict"]
    text: str
    severity: Literal["low", "medium", "high"] = "medium"
    evidence_segment_ids: list[str] = Field(default_factory=list)


class MeetingAnalysis(StrictModel):
    summary: str
    decisions: list[Decision] = Field(default_factory=list)
    action_items: list[ActionItem] = Field(default_factory=list)
    open_questions: list[str] = Field(default_factory=list)
    anomalies: list[Anomaly] = Field(default_factory=list)
    clarifications_needed: list[ClarificationNeeded] = Field(default_factory=list)


class Employee(StrictModel):
    employee_id: str
    name: str
    email: str
    designation: str
    team: str
    avatar_url: str | None = None
    timezone: str
    contact_handle: str


class ProjectStakeholder(StrictModel):
    role: str
    employee: Employee


class WorkspaceProject(StrictModel):
    project_id: str
    name: str
    description: str
    status: str
    team: str
    stakeholders: list[ProjectStakeholder] = Field(default_factory=list)


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


class DocSourceUpdate(StrictModel):
    title: str = Field(min_length=1, max_length=240)
    team: str = Field(min_length=1, max_length=120)
    source_type: DocSourceType
    body: str = Field(min_length=1, max_length=50_000)


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
