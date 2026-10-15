from datetime import UTC, datetime
from uuid import uuid4

from .fixtures import load_fixture
from .models import (
    AuthContext,
    CalendarEventCreate,
    CalendarEventItem,
    MeetingAnalysis,
    MeetingRecord,
    MeetingTranscriptInput,
    TranscriptSegment,
)
from .storage.base import KnowledgeStore

_created_events: list[dict[str, object]] = []


def _allowed(row: dict[str, object], auth: AuthContext) -> bool:
    if row["tenant_id"] != auth.tenant_id:
        return False
    principals = row.get("acl_principals", [])
    if not isinstance(principals, list):
        return False
    return bool(set(principals) & set(auth.principals))


def _organizer_initials(name: str) -> str:
    parts = [part for part in name.split() if part]
    if not parts:
        return "DU"
    if len(parts) == 1:
        return parts[0][:2].upper()
    return f"{parts[0][0]}{parts[-1][0]}".upper()


def list_calendar_events(
    auth: AuthContext,
    project_id: str | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
) -> list[CalendarEventItem]:
    result: list[CalendarEventItem] = []
    rows = load_fixture("calendar/events.json") + _created_events
    for raw in rows:
        if not _allowed(raw, auth):
            continue
        payload = {
            key: value
            for key, value in raw.items()
            if key not in {"tenant_id", "acl_principals"}
        }
        item = CalendarEventItem.model_validate(payload)
        if project_id and item.project_id != project_id:
            continue
        if date_from and item.started_at < date_from:
            continue
        if date_to and item.started_at >= date_to:
            continue
        result.append(item)
    return sorted(result, key=lambda row: row.started_at)


def create_calendar_event(
    store: KnowledgeStore,
    auth: AuthContext,
    payload: CalendarEventCreate,
) -> CalendarEventItem:
    if payload.ended_at <= payload.started_at:
        raise ValueError("Meeting end time must be after start time")

    organizer = auth.name or auth.user_id.replace("-", " ").title() or "Demo User"
    event_id = f"cal-{uuid4().hex[:8]}"
    meeting_id = f"M-{uuid4().hex[:8].upper()}"
    participants = payload.attendees or [organizer]
    location = payload.location
    if payload.video_meeting and not location:
        location = "Lotus video room"

    description = payload.description.strip()
    if payload.attendees:
        attendee_line = "Attendees: " + ", ".join(payload.attendees)
        description = f"{description}\n\n{attendee_line}".strip()

    item = CalendarEventItem(
        event_id=event_id,
        meeting_id=meeting_id,
        project_id=payload.project_id,
        title=payload.title.strip(),
        organizer=organizer,
        organizer_initials=_organizer_initials(organizer),
        location=location,
        description=description or "No additional details provided.",
        started_at=payload.started_at,
        ended_at=payload.ended_at,
    )

    segment = TranscriptSegment(
        segment_id=f"{meeting_id.lower()}-s1",
        start_ms=0,
        end_ms=max(int((payload.ended_at - payload.started_at).total_seconds() * 1000), 1000),
        speaker=organizer,
        text=f"Scheduled meeting: {item.title}.",
    )
    transcript = MeetingTranscriptInput(
        calendar_event_id=event_id,
        title=item.title,
        project_id=item.project_id,
        team="Payments",
        started_at=item.started_at,
        ended_at=item.ended_at,
        participants=participants,
        language_code="en",
        recording_url=f"fixture://recordings/{meeting_id}",
        segments=[segment],
    )
    analysis = MeetingAnalysis(
        summary=f"New meeting scheduled: {item.title}.",
        open_questions=["Capture decisions after the meeting completes."],
    )
    record = store.upsert_meeting(meeting_id, auth, transcript)
    record.analysis = analysis
    record.status = "processed"
    record.updated_at = datetime.now(UTC)
    store.save_meeting(record, auth)

    _created_events.append(
        {
            **item.model_dump(),
            "tenant_id": auth.tenant_id,
            "acl_principals": list(auth.principals),
        }
    )
    return item
