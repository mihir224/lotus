from datetime import datetime
from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from .auth import get_auth_context
from .config import get_settings
from .calendar import list_calendar_events
from .meetings import process_meeting
from .models import (
    AuthContext,
    CalendarEventItem,
    ChatRequest,
    GroundedAnswer,
    MeetingListItem,
    MeetingRecord,
    MeetingTranscriptInput,
)
from .service import answer_chat
from .storage import get_store

settings = get_settings()
app = FastAPI(title="Lotus API", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type", "X-Lotus-Tenant", "X-Lotus-User"],
)


@app.get("/v1/healthz")
def health() -> dict[str, str]:
    return {"status": "ok", "service": settings.app_name}


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
