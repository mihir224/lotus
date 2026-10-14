import logging
from contextlib import asynccontextmanager
from datetime import datetime
from time import perf_counter
from typing import Annotated
from uuid import uuid4

from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.requests import Request

from .auth import get_auth_context
from .calendar import list_calendar_events
from .config import get_settings
from .meetings import process_meeting, summarize_meeting
from .models import (
    AuthConfig,
    AuthContext,
    AuthenticatedUser,
    CalendarEventItem,
    ChatRequest,
    GroundedAnswer,
    MeetingListItem,
    MeetingRecord,
    MeetingTranscriptInput,
)
from .rate_limit import FixedWindowRateLimiter
from .service import answer_chat
from .storage import get_store

settings = get_settings()
logger = logging.getLogger("uvicorn.error.lotus")
agent_rate_limiter = FixedWindowRateLimiter(
    requests=settings.agent_rate_limit_requests,
    window_seconds=settings.agent_rate_limit_window_seconds,
)


@asynccontextmanager
async def lifespan(_: FastAPI):
    logger.info(
        "lotus.startup runtime=%s store=%s location=%s model=%s embedding_model=%s",
        settings.runtime_mode,
        settings.store_backend,
        settings.google_cloud_location,
        settings.generation_model,
        settings.active_embedding_model,
    )
    yield
    logger.info("lotus.shutdown")


app = FastAPI(title="Lotus API", version="0.1.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["Authorization", "Content-Type", "X-Lotus-Tenant", "X-Lotus-User"],
)


@app.middleware("http")
async def log_request(request: Request, call_next):
    request_id = uuid4().hex[:12]
    started = perf_counter()
    logger.info(
        "http.start request_id=%s method=%s path=%s",
        request_id,
        request.method,
        request.url.path,
    )
    try:
        response = await call_next(request)
    except Exception:
        logger.exception(
            "http.error request_id=%s method=%s path=%s duration_ms=%.1f",
            request_id,
            request.method,
            request.url.path,
            (perf_counter() - started) * 1000,
        )
        raise
    response.headers["X-Request-ID"] = request_id
    logger.info(
        "http.complete request_id=%s method=%s path=%s status=%s duration_ms=%.1f",
        request_id,
        request.method,
        request.url.path,
        response.status_code,
        (perf_counter() - started) * 1000,
    )
    return response


@app.get("/v1/healthz")
def health() -> dict[str, str]:
    return {"status": "ok", "service": settings.app_name}


@app.get("/v1/auth/config", response_model=AuthConfig)
def auth_config() -> AuthConfig:
    return AuthConfig(
        mode=settings.auth_mode,
        google_client_id=(
            settings.google_oauth_client_id if settings.auth_mode == "google" else None
        ),
    )


@app.get("/v1/auth/me", response_model=AuthenticatedUser)
def authenticated_user(
    auth: Annotated[AuthContext, Depends(get_auth_context)],
) -> AuthenticatedUser:
    return AuthenticatedUser(user_id=auth.user_id, email=auth.email, name=auth.name)


@app.get("/v1/readyz")
def ready() -> dict[str, object]:
    store = get_store()
    return {
        "status": "ready" if store.ready() else "not_ready",
        "runtime": settings.runtime_mode,
        "store": settings.store_backend,
        "gcp_configured": bool(settings.google_cloud_project),
        "location": settings.google_cloud_location,
    }


@app.post("/v1/chat/messages", response_model=GroundedAnswer)
def chat(
    request: ChatRequest,
    auth: Annotated[AuthContext, Depends(get_auth_context)],
) -> GroundedAnswer:
    retry_after = agent_rate_limiter.check(f"{auth.tenant_id}:{auth.user_id}")
    if retry_after is not None:
        raise HTTPException(
            status_code=429,
            detail="Agent request limit reached; try again shortly",
            headers={"Retry-After": str(retry_after)},
        )
    return answer_chat(request, auth)


@app.post("/v1/meetings/{meeting_id}/process", response_model=MeetingRecord)
def process_meeting_endpoint(
    meeting_id: str,
    transcript: MeetingTranscriptInput,
    auth: Annotated[AuthContext, Depends(get_auth_context)],
) -> MeetingRecord:
    if transcript.project_id.strip() == "":
        raise HTTPException(status_code=422, detail="project_id is required")
    return process_meeting(get_store(), meeting_id, auth, transcript)


@app.get("/v1/meetings/{meeting_id}", response_model=MeetingRecord)
def get_meeting_endpoint(
    meeting_id: str,
    auth: Annotated[AuthContext, Depends(get_auth_context)],
) -> MeetingRecord:
    record = get_store().get_meeting(meeting_id, auth)
    if record is None:
        raise HTTPException(status_code=404, detail="Meeting not found")
    return record


@app.post("/v1/meetings/{meeting_id}/summarize", response_model=MeetingRecord)
def summarize_meeting_endpoint(
    meeting_id: str,
    auth: Annotated[AuthContext, Depends(get_auth_context)],
) -> MeetingRecord:
    record = summarize_meeting(get_store(), meeting_id, auth)
    if record is None:
        raise HTTPException(status_code=404, detail="Meeting transcript not found")
    return record


@app.get("/v1/calendar/events", response_model=list[CalendarEventItem])
def list_calendar_events_endpoint(
    auth: Annotated[AuthContext, Depends(get_auth_context)],
    project_id: str | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
) -> list[CalendarEventItem]:
    return list_calendar_events(auth, project_id, date_from, date_to)


@app.get("/v1/meetings", response_model=list[MeetingListItem])
def list_meetings_endpoint(
    auth: Annotated[AuthContext, Depends(get_auth_context)],
    project_id: str | None = None,
    team: str | None = None,
    topic: str | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
) -> list[MeetingListItem]:
    rows = get_store().list_meetings(auth, project_id, team, date_from, date_to)
    if topic:
        needle = topic.casefold()
        rows = [row for row in rows if needle in row.title.casefold()]
    return rows
