import asyncio
import hashlib
import logging
from datetime import UTC, datetime

from google.adk.runners import InMemoryRunner
from google.genai import types

from .agents.registry import build_meeting_analysis_agent
from .config import get_settings
from .meeting_analysis import analyze_transcript, build_clarifications, detect_content_anomalies
from .models import (
    AuthContext,
    MeetingAnalysis,
    MeetingAnalysisMetadata,
    MeetingRecord,
    MeetingTranscriptInput,
)
from .storage.base import KnowledgeStore

logger = logging.getLogger("uvicorn.error.lotus.meetings")


def _input_hash(transcript: MeetingTranscriptInput) -> str:
    payload = transcript.model_dump_json(exclude_none=False)
    return hashlib.sha256(payload.encode()).hexdigest()


async def _live_analysis(transcript: MeetingTranscriptInput) -> MeetingAnalysis:
    settings = get_settings()
    agent = build_meeting_analysis_agent(settings)
    runner = InMemoryRunner(agent=agent, app_name="lotus")
    session = await runner.session_service.create_session(app_name="lotus", user_id="meeting")
    prompt = "Timestamped transcript JSON:\n" + transcript.model_dump_json()
    final_text = ""
    async with asyncio.timeout(settings.agent_timeout_seconds):
        async for event in runner.run_async(
            user_id="meeting",
            session_id=session.id,
            new_message=types.Content(role="user", parts=[types.Part(text=prompt)]),
        ):
            if event.is_final_response() and event.content:
                final_text = "".join(part.text or "" for part in event.content.parts)
    analysis = MeetingAnalysis.model_validate_json(final_text)
    valid_segments = {segment.segment_id for segment in transcript.segments}
    for decision in analysis.decisions:
        if not set(decision.evidence_segment_ids).issubset(valid_segments):
            raise ValueError("Meeting analysis referenced an unknown segment")
    for action in analysis.action_items:
        if not set(action.evidence_segment_ids).issubset(valid_segments):
            raise ValueError("Meeting analysis referenced an unknown segment")
    transcript_text = " ".join(segment.text for segment in transcript.segments)
    analysis.anomalies = detect_content_anomalies(
        analysis.action_items, analysis.open_questions, transcript_text
    )
    analysis.clarifications_needed = build_clarifications(
        analysis.open_questions, analysis.anomalies
    )
    return analysis


def process_meeting(
    store: KnowledgeStore,
    meeting_id: str,
    auth: AuthContext,
    transcript: MeetingTranscriptInput,
) -> MeetingRecord:
    settings = get_settings()
    transcript_hash = _input_hash(transcript)
    active_model = (
        settings.generation_model
        if settings.runtime_mode in {"agent_platform", "vertex"}
        else "fixture:meeting-analysis-v1"
    )
    existing = store.get_meeting(meeting_id, auth)
    if (
        existing
        and existing.status == "processed"
        and existing.analysis_metadata
        and existing.analysis_metadata.input_hash == transcript_hash
        and existing.analysis_metadata.model == active_model
    ):
        return existing
    record = store.upsert_meeting(meeting_id, auth, transcript)
    method = "fixture"
    if settings.runtime_mode in {"agent_platform", "vertex"}:
        try:
            record.analysis = asyncio.run(_live_analysis(transcript))
            method = "agent_platform"
        except Exception as exc:
            logger.warning("meeting_analysis.fallback reason=%s", type(exc).__name__)
            record.analysis = analyze_transcript(transcript)
            method = "fallback"
    else:
        record.analysis = analyze_transcript(transcript)
    record.analysis_metadata = MeetingAnalysisMetadata(
        method=method,
        model=active_model,
        input_hash=transcript_hash,
        generated_at=datetime.now(UTC),
    )
    record.status = "processed"
    record.updated_at = datetime.now(UTC)
    return store.save_meeting(record, auth)


def summarize_meeting(
    store: KnowledgeStore,
    meeting_id: str,
    auth: AuthContext,
) -> MeetingRecord | None:
    """Idempotently analyze the transcript already linked to a calendar event."""
    record = store.get_meeting(meeting_id, auth)
    if record is None:
        return None
    return process_meeting(store, meeting_id, auth, record.transcript)
