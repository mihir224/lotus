from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Route(StrEnum):
    KNOWLEDGE = "knowledge"
    MEETING = "meeting"
    CODE = "code"
    DOCUMENT = "document"
    RESEARCH = "research"


class Mode(StrEnum):
    AUTO = "auto"
    ASK_COMPANY = "ask_company"
    MEETING = "meeting"
    CODE = "code"
    DOCUMENT = "document"
    RESEARCH = "research"


class AuthContext(StrictModel):
    tenant_id: str
    user_id: str
    principals: tuple[str, ...]


class ChatRequest(StrictModel):
    message: str = Field(min_length=1, max_length=8_000)
    project_id: str = Field(min_length=1, max_length=128)
    mode: Mode = Mode.AUTO
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


class RouteDecision(StrictModel):
    route: Route
    confidence: float = Field(ge=0, le=1)
    reason: str
    live_retrieval: bool = False


class GroundedAnswer(StrictModel):
    answer: str
    evidence: list[Evidence]
    scope: Scope
    uncertainty: list[str] = Field(default_factory=list)
    next_action: str | None = None
    route: RouteDecision
