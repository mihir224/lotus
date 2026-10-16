from datetime import datetime
from uuid import uuid4

from .models import (
    AuthContext,
    CalendarEventCreate,
    CalendarEventItem,
    MeetingRecord,
)
from .storage.base import KnowledgeStore


def _organizer_initials(name: str) -> str:
    parts = [part for part in name.split() if part]
    if not parts:
        return "DU"
    if len(parts) == 1:
        return parts[0][:2].upper()
    return f"{parts[0][0]}{parts[-1][0]}".upper()


def list_calendar_events(
    store: KnowledgeStore,
    auth: AuthContext,
    project_id: str | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
) -> list[CalendarEventItem]:
    return store.list_calendar_events(auth, project_id, date_from, date_to)


def is_synthetic_calendar_placeholder(record: MeetingRecord | None) -> bool:
    """Identify legacy calendar rows that contain no real transcript content."""
    if record is None or len(record.transcript.segments) != 1:
        return False
    segment = record.transcript.segments[0]
    return segment.text.strip() == f"Scheduled meeting: {record.transcript.title}."


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

    # Scheduling metadata is not transcript content. The processing endpoint creates a meeting
    # record later, when a real transcript is available.
    store.upsert_calendar_event(auth, item)
    return item
