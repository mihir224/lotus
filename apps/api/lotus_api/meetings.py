from datetime import UTC, datetime

from .meeting_analysis import analyze_transcript
from .models import AuthContext, MeetingRecord, MeetingTranscriptInput
from .storage.base import KnowledgeStore


def process_meeting(
    store: KnowledgeStore,
    meeting_id: str,
    auth: AuthContext,
    transcript: MeetingTranscriptInput,
) -> MeetingRecord:
    existing = store.get_meeting(meeting_id, auth)
    if existing and existing.status == "processed" and existing.transcript == transcript:
        return existing
    record = store.upsert_meeting(meeting_id, auth, transcript)
    record.analysis = analyze_transcript(transcript)
    record.status = "processed"
    record.updated_at = datetime.now(UTC)
    return store.save_meeting(record, auth)
