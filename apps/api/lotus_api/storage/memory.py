import hashlib
import json
import math
from datetime import UTC, datetime
from typing import Any

from ..chunking import chunk_transcript
from ..config import Settings
from ..embeddings import Embedder
from ..models import (
    AuthContext,
    Evidence,
    MeetingAnalysis,
    MeetingListItem,
    MeetingRecord,
    MeetingTranscriptInput,
    Scope,
)


def _cosine(left: list[float], right: list[float]) -> float:
    denominator = math.sqrt(sum(x * x for x in left)) * math.sqrt(sum(x * x for x in right))
    return sum(x * y for x, y in zip(left, right, strict=True)) / (denominator or 1.0)


def _allowed(row: dict[str, Any], auth: AuthContext, project_id: str) -> bool:
    return (
        row["tenant_id"] == auth.tenant_id
        and row["project_id"] == project_id
        and bool(set(row["acl_principals"]) & set(auth.principals))
    )


class MemoryKnowledgeStore:
    def __init__(self, settings: Settings, embedder: Embedder):
        self.settings = settings
        self.embedder = embedder
        self.documents: dict[str, dict[str, Any]] = {}
        self.meetings: dict[str, MeetingRecord] = {}
        self.transcript_chunks: dict[str, list[dict[str, Any]]] = {}
        self.seed()

    def ready(self) -> bool:
        return True

    def _load(self, relative: str) -> Any:
        return json.loads((self.settings.fixture_dir / relative).read_text(encoding="utf-8"))

    def seed(self) -> dict[str, int]:
        documents = self._load("enterprise/documents.json")
        for document in documents:
            document = dict(document)
            document["embedding_model"] = self.embedder.model_id
            document["embedding"] = self.embedder.embed_documents([document["chunk_text"]])[0]
            self.documents[document["chunk_id"]] = document

        for raw in self._load("meetings/meetings.json"):
            meeting_id = raw["meeting_id"]
            transcript = MeetingTranscriptInput.model_validate(raw["transcript"])
            analysis = (
                MeetingAnalysis.model_validate(raw["analysis"]) if raw.get("analysis") else None
            )
            record = MeetingRecord(
                meeting_id=meeting_id,
                tenant_id=raw["tenant_id"],
                transcript=transcript,
                analysis=analysis,
                status="processed" if analysis else "received",
                updated_at=datetime.now(UTC),
            )
            self.meetings[meeting_id] = record
            self._index_transcript(record, raw.get("acl_principals", ["group:demo"]))
        return {"documents": len(self.documents), "meetings": len(self.meetings)}

    def _index_transcript(self, record: MeetingRecord, principals: list[str]) -> None:
        chunks = chunk_transcript(record.transcript.segments, target_words=70)
        vectors = self.embedder.embed_documents([chunk.text for chunk in chunks])
        self.transcript_chunks[record.meeting_id] = [
            {
                "chunk_id": hashlib.sha256(
                    f"{record.meeting_id}:{chunk.index}:{chunk.text}".encode()
                ).hexdigest()[:24],
                "tenant_id": record.tenant_id,
                "project_id": record.transcript.project_id,
                "team": record.transcript.team,
                "meeting_id": record.meeting_id,
                "title": record.transcript.title,
                "started_at": record.transcript.started_at,
                "start_ms": chunk.start_ms,
                "end_ms": chunk.end_ms,
                "segment_ids": list(chunk.segment_ids),
                "speakers": list(chunk.speakers),
                "chunk_text": chunk.text,
                "acl_principals": principals,
                "embedding_model": self.embedder.model_id,
                "embedding": vector,
            }
            for chunk, vector in zip(chunks, vectors, strict=True)
        ]

    def search_documents(
        self,
        query: str,
        auth: AuthContext,
        project_id: str,
        top_k: int = 8,
        source_types: tuple[str, ...] | list[str] = (),
    ) -> list[Evidence]:
        query_vector = self.embedder.embed_query(query)
        scored = []
        normalized_query = query.casefold()
        for row in self.documents.values():
            if not _allowed(row, auth, project_id):
                continue
            if row["embedding_model"] != self.embedder.model_id:
                continue
            if source_types and row["source_type"] not in source_types:
                continue
            score = _cosine(query_vector, row["embedding"])
            exact_source = row["source_id"].casefold() in normalized_query
            if score >= 0.2 or exact_source:
                scored.append((1.0 if exact_source else score, row))
        scored.sort(key=lambda item: (-item[0], item[1]["source_id"]))
        return [
            Evidence(
                source_id=row["source_id"],
                source_system=row["source_system"],
                source_type=row["source_type"],
                title=row["title"],
                uri=row.get("source_uri"),
                snippet=row["chunk_text"],
                section=row.get("section_path"),
                updated_at=row.get("source_updated_at"),
                retrieval_method="vector_fixture",
                scope=Scope(tenant_id=auth.tenant_id, project_id=project_id),
                score=round(score, 4),
                version=row.get("source_version"),
            )
            for score, row in scored[:top_k]
        ]

    def search_transcripts(
        self,
        query: str,
        auth: AuthContext,
        project_id: str,
        top_k: int = 8,
        meeting_id: str | None = None,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
    ) -> list[Evidence]:
        query_vector = self.embedder.embed_query(query)
        scored = []
        for rows in self.transcript_chunks.values():
            for row in rows:
                if not _allowed(row, auth, project_id):
                    continue
                if meeting_id and row["meeting_id"] != meeting_id:
                    continue
                if date_from and row["started_at"] < date_from:
                    continue
                if date_to and row["started_at"] >= date_to:
                    continue
                if row["embedding_model"] != self.embedder.model_id:
                    continue
                scored.append((_cosine(query_vector, row["embedding"]), row))
        scored.sort(key=lambda item: (-item[0], item[1]["meeting_id"], item[1]["start_ms"]))
        return [
            Evidence(
                source_id=row["chunk_id"],
                source_system="meeting",
                source_type="transcript",
                title=row["title"],
                uri=f"lotus://meetings/{row['meeting_id']}?t={row['start_ms']}",
                snippet=row["chunk_text"],
                section=f"{row['start_ms']}–{row['end_ms']} ms",
                updated_at=row["started_at"].isoformat(),
                retrieval_method="vector_fixture",
                scope=Scope(
                    tenant_id=auth.tenant_id,
                    project_id=project_id,
                    meeting_id=row["meeting_id"],
                ),
                score=round(score, 4),
                meeting_id=row["meeting_id"],
                start_ms=row["start_ms"],
                end_ms=row["end_ms"],
            )
            for score, row in scored[:top_k]
            if score > 0
        ]

    def upsert_meeting(
        self,
        meeting_id: str,
        auth: AuthContext,
        transcript: MeetingTranscriptInput,
    ) -> MeetingRecord:
        record = MeetingRecord(
            meeting_id=meeting_id,
            tenant_id=auth.tenant_id,
            transcript=transcript,
            status="received",
            updated_at=datetime.now(UTC),
        )
        self.meetings[meeting_id] = record
        self._index_transcript(record, list(auth.principals))
        return record

    def get_meeting(self, meeting_id: str, auth: AuthContext) -> MeetingRecord | None:
        record = self.meetings.get(meeting_id)
        if record is None or record.tenant_id != auth.tenant_id:
            return None
        return record

    def save_meeting(self, record: MeetingRecord, auth: AuthContext) -> MeetingRecord:
        if record.tenant_id != auth.tenant_id:
            raise PermissionError("Meeting belongs to another tenant")
        self.meetings[record.meeting_id] = record
        return record

    def list_meetings(
        self,
        auth: AuthContext,
        project_id: str | None = None,
        team: str | None = None,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
    ) -> list[MeetingListItem]:
        result = []
        for record in self.meetings.values():
            item = record.transcript
            if record.tenant_id != auth.tenant_id:
                continue
            if project_id and item.project_id != project_id:
                continue
            if team and item.team.casefold() != team.casefold():
                continue
            if date_from and item.started_at < date_from:
                continue
            if date_to and item.started_at >= date_to:
                continue
            result.append(
                MeetingListItem(
                    meeting_id=record.meeting_id,
                    calendar_event_id=item.calendar_event_id,
                    title=item.title,
                    project_id=item.project_id,
                    team=item.team,
                    started_at=item.started_at,
                    ended_at=item.ended_at,
                    language_code=item.language_code,
                    status=record.status,
                )
            )
        return sorted(result, key=lambda item: item.started_at, reverse=True)
