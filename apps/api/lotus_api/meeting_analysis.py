import re

from .models import ActionItem, Anomaly, Decision, MeetingAnalysis, MeetingTranscriptInput

DECISION = re.compile(r"\bdecision:\s*(.+)", re.IGNORECASE)
ACTION = re.compile(r"\baction item:\s*(.+)", re.IGNORECASE)
OPEN_QUESTION = re.compile(r"\bopen question:\s*(.+)", re.IGNORECASE)
OWNER = re.compile(r"\b([A-Z][a-z]+)\s+(?:owns it|will|to)\b")
DUE_DATE = re.compile(r"\b(?:by|due)\s+([A-Z][a-z]+\s+\w+|\d{4}-\d{2}-\d{2})\b")


def analyze_transcript(transcript: MeetingTranscriptInput) -> MeetingAnalysis:
    decisions: list[Decision] = []
    actions: list[ActionItem] = []
    questions: list[str] = []
    for segment in transcript.segments:
        if match := DECISION.search(segment.text):
            decisions.append(
                Decision(
                    text=match.group(1).strip(),
                    timestamp_ms=segment.start_ms,
                    evidence_segment_ids=[segment.segment_id],
                )
            )
        if match := ACTION.search(segment.text):
            owner_match = OWNER.search(segment.text)
            due_match = DUE_DATE.search(segment.text)
            actions.append(
                ActionItem(
                    text=match.group(1).strip(),
                    owner=owner_match.group(1) if owner_match else None,
                    due_date=due_match.group(1) if due_match else None,
                    timestamp_ms=segment.start_ms,
                    evidence_segment_ids=[segment.segment_id],
                )
            )
        if match := OPEN_QUESTION.search(segment.text):
            questions.append(match.group(1).strip())

    all_text = " ".join(segment.text for segment in transcript.segments)
    if not decisions:
        decisions = [
            Decision(
                text=segment.text,
                timestamp_ms=segment.start_ms,
                evidence_segment_ids=[segment.segment_id],
            )
            for segment in transcript.segments
            if "agreed" in segment.text.casefold()
        ]
    summary = " ".join(segment.text for segment in transcript.segments[:2])
    anomalies = detect_content_anomalies(actions, questions, all_text)
    return MeetingAnalysis(
        summary=summary,
        decisions=decisions,
        action_items=actions,
        open_questions=questions,
        anomalies=anomalies,
    )


def detect_content_anomalies(
    actions: list[ActionItem],
    open_questions: list[str],
    transcript_text: str,
) -> list[Anomaly]:
    anomalies: list[Anomaly] = []
    for action in actions:
        if not action.owner:
            anomalies.append(
                Anomaly(
                    anomaly_type="unowned_action",
                    severity="high",
                    description=f"Action item has no owner: {action.text}",
                    evidence_segment_ids=action.evidence_segment_ids,
                )
            )
        if not action.due_date:
            anomalies.append(
                Anomaly(
                    anomaly_type="missing_due_date",
                    severity="medium",
                    description=f"Action item has no due date: {action.text}",
                    evidence_segment_ids=action.evidence_segment_ids,
                )
            )
    for question in open_questions:
        anomalies.append(
            Anomaly(
                anomaly_type="unresolved_question",
                severity="medium",
                description=f"Open question remains unresolved: {question}",
            )
        )
    lowered = transcript_text.casefold()
    if "decision:" in lowered and ("five attempts" in lowered or "fixed delay" in lowered):
        anomalies.append(
            Anomaly(
                anomaly_type="document_conflict",
                severity="high",
                description=(
                    "Meeting decision may conflict with ADR-017, which requires full jitter "
                    "and three total attempts."
                ),
            )
        )
    return anomalies
