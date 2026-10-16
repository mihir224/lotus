from lotus_api.meeting_analysis import analyze_transcript
from lotus_api.models import MeetingTranscriptInput


def test_analysis_detects_supported_content_gaps() -> None:
    transcript = MeetingTranscriptInput.model_validate(
        {
            "calendar_event_id": "cal-test",
            "title": "Retry review",
            "project_id": "payments",
            "team": "Payments",
            "started_at": "2026-10-10T10:00:00Z",
            "ended_at": "2026-10-10T10:30:00Z",
            "participants": ["Asha"],
            "segments": [
                {
                    "segment_id": "s1",
                    "start_ms": 0,
                    "end_ms": 1000,
                    "speaker": "Asha",
                    "text": "Decision: use fixed delay with five attempts.",
                },
                {
                    "segment_id": "s2",
                    "start_ms": 1000,
                    "end_ms": 2000,
                    "speaker": "Asha",
                    "text": "Action item: update the retry client.",
                },
                {
                    "segment_id": "s3",
                    "start_ms": 2000,
                    "end_ms": 3000,
                    "speaker": "Asha",
                    "text": "Open question: who approves the rollout?",
                },
            ],
        }
    )
    kinds = {item.anomaly_type for item in analyze_transcript(transcript).anomalies}
    assert kinds == {
        "unowned_action",
        "missing_due_date",
        "unresolved_question",
        "document_conflict",
    }
