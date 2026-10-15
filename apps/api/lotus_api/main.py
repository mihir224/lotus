import logging
import queue
import threading
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path
from time import perf_counter
from typing import Annotated
from uuid import uuid4

from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.requests import Request
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles

from .auth import get_auth_context
from .calendar import create_calendar_event, list_calendar_events
from .config import get_settings
from .docs import create_doc_source, get_doc_page, get_docs_catalog, search_docs
from .meetings import process_meeting, summarize_meeting
from .models import (
    AuthConfig,
    AuthContext,
    AuthenticatedUser,
    BoardIssueCreate,
    BoardIssueItem,
    BoardIssueUpdate,
    CalendarEventCreate,
    CalendarEventItem,
    ChatRequest,
    DocCatalogResponse,
    DocPageDetail,
    DocSearchHit,
    DocSourceCreate,
    GroundedAnswer,
    MeetingListItem,
    MeetingRecord,
    MeetingTranscriptInput,
    RunEvent,
    WorkBoardResponse,
)
from .rate_limit import FixedWindowRateLimiter
from .service import answer_chat, stream_chat
from .storage import get_store
from .telemetry import configure_telemetry
from .work_board import create_board_issue, get_work_board
from .work_board import update_board_issue as patch_board_issue

settings = get_settings()
logger = logging.getLogger("uvicorn.error.lotus")
agent_rate_limiter = FixedWindowRateLimiter(
    requests=settings.agent_rate_limit_requests,
    window_seconds=settings.agent_rate_limit_window_seconds,
)


@asynccontextmanager
async def lifespan(_: FastAPI):
    configure_telemetry(settings)
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
    allow_methods=["GET", "POST", "PATCH"],
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
    return AuthenticatedUser(
        user_id=auth.user_id,
        email=auth.email,
        name=auth.name,
        designation=auth.designation,
        picture_url=auth.picture_url,
    )


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


@app.post("/v1/chat/stream")
def chat_stream(
    request: ChatRequest,
    auth: Annotated[AuthContext, Depends(get_auth_context)],
) -> StreamingResponse:
    retry_after = agent_rate_limiter.check(f"{auth.tenant_id}:{auth.user_id}")
    if retry_after is not None:
        raise HTTPException(
            status_code=429,
            detail="Agent request limit reached; try again shortly",
            headers={"Retry-After": str(retry_after)},
        )

    events: queue.Queue[RunEvent | None] = queue.Queue()

    def worker() -> None:
        try:
            stream_chat(request, auth, events.put)
        finally:
            events.put(None)

    threading.Thread(target=worker, name="lotus-chat-stream", daemon=True).start()

    def generate():
        while True:
            try:
                item = events.get(timeout=15)
            except queue.Empty:
                yield "event: heartbeat\ndata: {}\n\n"
                continue
            if item is None:
                break
            payload = item.model_dump_json()
            yield f"event: {item.event_type}\ndata: {payload}\n\n"

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )


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
    return list_calendar_events(get_store(), auth, project_id, date_from, date_to)


@app.post("/v1/calendar/events", response_model=CalendarEventItem)
def create_calendar_event_endpoint(
    payload: CalendarEventCreate,
    auth: Annotated[AuthContext, Depends(get_auth_context)],
) -> CalendarEventItem:
    try:
        return create_calendar_event(get_store(), auth, payload)
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error


@app.get("/v1/work-board", response_model=WorkBoardResponse)
def get_work_board_endpoint(
    auth: Annotated[AuthContext, Depends(get_auth_context)],
    project_id: str | None = None,
    team_id: str | None = None,
) -> WorkBoardResponse:
    return get_work_board(get_store(), auth, project_id, team_id)


@app.post("/v1/work-board/issues", response_model=BoardIssueItem)
def create_work_board_issue_endpoint(
    payload: BoardIssueCreate,
    auth: Annotated[AuthContext, Depends(get_auth_context)],
) -> BoardIssueItem:
    try:
        return create_board_issue(get_store(), auth, payload)
    except LookupError:
        raise HTTPException(status_code=404, detail="Team not found") from None
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error


@app.patch("/v1/work-board/issues/{issue_key}", response_model=BoardIssueItem)
def patch_work_board_issue_endpoint(
    issue_key: str,
    payload: BoardIssueUpdate,
    auth: Annotated[AuthContext, Depends(get_auth_context)],
) -> BoardIssueItem:
    try:
        return patch_board_issue(get_store(), issue_key, auth, payload)
    except LookupError:
        raise HTTPException(status_code=404, detail="Issue not found") from None
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error


@app.get("/v1/docs/catalog", response_model=DocCatalogResponse)
def docs_catalog_endpoint(
    auth: Annotated[AuthContext, Depends(get_auth_context)],
    project_id: str = "payments",
) -> DocCatalogResponse:
    return get_docs_catalog(get_store(), auth, project_id)


@app.get("/v1/docs/search", response_model=list[DocSearchHit])
def docs_search_endpoint(
    auth: Annotated[AuthContext, Depends(get_auth_context)],
    q: str,
    project_id: str = "payments",
) -> list[DocSearchHit]:
    return search_docs(get_store(), auth, project_id, q)


@app.get("/v1/docs/sources/{source_id}", response_model=DocPageDetail)
def docs_page_endpoint(
    source_id: str,
    auth: Annotated[AuthContext, Depends(get_auth_context)],
    project_id: str = "payments",
) -> DocPageDetail:
    try:
        return get_doc_page(get_store(), auth, project_id, source_id)
    except LookupError:
        raise HTTPException(status_code=404, detail="Document not found") from None


@app.post("/v1/docs/sources", response_model=DocPageDetail)
def docs_create_endpoint(
    payload: DocSourceCreate,
    auth: Annotated[AuthContext, Depends(get_auth_context)],
) -> DocPageDetail:
    try:
        return create_doc_source(get_store(), auth, payload)
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error


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


# Cloud Run serves the built Vite app and API from one HTTPS origin. Keep this
# mount last so it can never shadow the explicit /v1 routes above.
web_dist = Path(__file__).resolve().parents[3] / "apps" / "web" / "dist"
if web_dist.is_dir():
    app.mount("/", StaticFiles(directory=web_dist, html=True), name="web")
