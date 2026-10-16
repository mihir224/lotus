import hashlib
import json
import logging
import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import case, create_engine, delete, func, select, text
from sqlalchemy.orm import Session

from ..chunking import chunk_transcript
from ..config import Settings
from ..db_observability import instrument_database, record_retrieval
from ..embeddings import Embedder
from ..models import (
    AuthContext,
    BoardIssueItem,
    BoardIssueUpdate,
    CalendarEventItem,
    ChatMessageRecord,
    ChatSessionDetail,
    ChatSessionPage,
    ChatSessionSummary,
    Employee,
    Evidence,
    MeetingAnalysis,
    MeetingAnalysisMetadata,
    MeetingListItem,
    MeetingRecord,
    MeetingTranscriptInput,
    NavigationTarget,
    ProjectStakeholder,
    Scope,
    WorkspaceProject,
)
from .models import (
    BoardIssueRow,
    CalendarEventRow,
    ChatMessageRow,
    ChatSessionRow,
    DocumentEmbeddingRow,
    EmployeeRow,
    MeetingTranscriptRow,
    ProjectStakeholderRow,
    TranscriptEmbeddingRow,
    WorkspaceProjectRow,
)

logger = logging.getLogger("uvicorn.error.lotus.database")


class PostgresKnowledgeStore:
    def __init__(self, settings: Settings, embedder: Embedder):
        self.settings = settings
        self.embedder = embedder
        self.engine = create_engine(
            settings.database_connection_url,
            pool_pre_ping=True,
            pool_size=settings.db_pool_size,
            max_overflow=settings.db_max_overflow,
            pool_timeout=settings.db_pool_timeout_seconds,
            pool_recycle=settings.db_pool_recycle_seconds,
        )
        instrument_database(self.engine)

    def ready(self) -> bool:
        try:
            with self.engine.connect() as connection:
                connection.execute(text("SELECT 1"))
            logger.info("db.readiness store=postgres ready=true")
            return True
        except Exception as exc:
            logger.warning(
                "db.readiness store=postgres ready=false error=%s",
                type(exc).__name__,
            )
            return False

    def _load(self, relative: str) -> Any:
        return json.loads((self.settings.fixture_dir / relative).read_text(encoding="utf-8"))

    def seed(self) -> dict[str, int]:
        documents = self._load("enterprise/documents.json")
        vectors = self.embedder.embed_documents([row["chunk_text"] for row in documents])
        with Session(self.engine) as session:
            for payload, vector in zip(documents, vectors, strict=True):
                row = session.scalar(
                    select(DocumentEmbeddingRow).where(
                        DocumentEmbeddingRow.tenant_id == payload["tenant_id"],
                        DocumentEmbeddingRow.chunk_id == payload["chunk_id"],
                        DocumentEmbeddingRow.embedding_model == self.embedder.model_id,
                    )
                )
                values = {
                    **payload,
                    "metadata_json": payload.get("metadata", {}),
                    "content_hash": hashlib.sha256(payload["chunk_text"].encode()).hexdigest(),
                    "embedding_model": self.embedder.model_id,
                    "embedding": vector,
                }
                values.pop("metadata", None)
                if row is None:
                    session.add(DocumentEmbeddingRow(**values))
                else:
                    for key, value in values.items():
                        setattr(row, key, value)
            session.commit()

        auth = AuthContext(tenant_id="demo", user_id="seed", principals=("group:demo",))
        for raw in self._load("meetings/meetings.json"):
            record = self.upsert_meeting(
                raw["meeting_id"], auth, MeetingTranscriptInput.model_validate(raw["transcript"])
            )
            if raw.get("analysis"):
                record.analysis = MeetingAnalysis.model_validate(raw["analysis"])
                record.status = "processed"
                self.save_meeting(record, auth)

        calendar_rows = self._load("calendar/events.json")
        for raw in calendar_rows:
            payload = dict(raw)
            item = CalendarEventItem.model_validate(
                {
                    key: value
                    for key, value in payload.items()
                    if key not in {"tenant_id", "acl_principals"}
                }
            )
            self.upsert_calendar_event(
                AuthContext(
                    tenant_id=payload["tenant_id"],
                    user_id="seed",
                    principals=tuple(payload.get("acl_principals", ["group:demo"])),
                ),
                item,
                list(payload.get("acl_principals", ["group:demo"])),
            )

        board_rows = self._load("work_board/issues.json")
        for raw in board_rows:
            payload = dict(raw)
            issue = BoardIssueItem.model_validate(
                {
                    key: value
                    for key, value in payload.items()
                    if key not in {"tenant_id", "acl_principals"}
                }
            )
            self.upsert_board_issue(
                AuthContext(
                    tenant_id=payload["tenant_id"],
                    user_id="seed",
                    principals=tuple(payload.get("acl_principals", ["group:demo"])),
                ),
                issue,
                list(payload.get("acl_principals", ["group:demo"])),
            )
        people = self._load("enterprise/employees.json")
        projects = self._load("enterprise/projects.json")
        now = datetime.now(UTC)
        with Session(self.engine) as session:
            employee_rows: dict[str, EmployeeRow] = {}
            for payload in people:
                row = session.scalar(
                    select(EmployeeRow).where(
                        EmployeeRow.tenant_id == payload["tenant_id"],
                        EmployeeRow.employee_id == payload["employee_id"],
                    )
                )
                values = {**payload, "updated_at": now}
                if row is None:
                    row = EmployeeRow(**values)
                    session.add(row)
                    session.flush()
                else:
                    for key, value in values.items():
                        setattr(row, key, value)
                employee_rows[payload["employee_id"]] = row
            for payload in projects:
                stakeholders = payload.get("stakeholders", [])
                values = {key: value for key, value in payload.items() if key != "stakeholders"}
                values["updated_at"] = now
                row = session.scalar(
                    select(WorkspaceProjectRow).where(
                        WorkspaceProjectRow.tenant_id == payload["tenant_id"],
                        WorkspaceProjectRow.project_id == payload["project_id"],
                    )
                )
                if row is None:
                    row = WorkspaceProjectRow(**values)
                    session.add(row)
                    session.flush()
                else:
                    for key, value in values.items():
                        setattr(row, key, value)
                session.execute(
                    delete(ProjectStakeholderRow).where(
                        ProjectStakeholderRow.project_id == row.id
                    )
                )
                for link in stakeholders:
                    employee = employee_rows.get(link["employee_id"])
                    if employee:
                        session.add(
                            ProjectStakeholderRow(
                                project_id=row.id,
                                employee_id=employee.id,
                                role=link["role"],
                            )
                        )
            session.commit()
        return {
            "documents": len(documents),
            "meetings": len(self._load("meetings/meetings.json")),
            "calendar_events": len(calendar_rows),
            "board_issues": len(board_rows),
            "employees": len(people),
            "projects": len(projects),
        }

    def search_documents(
        self,
        query: str,
        auth: AuthContext,
        project_id: str,
        top_k: int = 8,
        source_types: tuple[str, ...] | list[str] = (),
    ) -> list[Evidence]:
        vector = self.embedder.embed_query(query)
        vector_distance = DocumentEmbeddingRow.embedding.cosine_distance(vector)
        exact_source = (
            func.strpos(func.lower(query), func.lower(DocumentEmbeddingRow.source_id)) > 0
        )
        distance = case((exact_source, 0.0), else_=vector_distance)
        statement = select(DocumentEmbeddingRow, distance.label("distance")).where(
            DocumentEmbeddingRow.tenant_id == auth.tenant_id,
            DocumentEmbeddingRow.project_id == project_id,
            DocumentEmbeddingRow.acl_principals.op("&&")(list(auth.principals)),
            DocumentEmbeddingRow.embedding_model == self.embedder.model_id,
            (vector_distance <= 0.75) | exact_source,
        )
        if source_types:
            statement = statement.where(DocumentEmbeddingRow.source_type.in_(source_types))
        statement = statement.order_by(distance).limit(top_k)
        with Session(self.engine) as session:
            rows = session.execute(statement).all()
        record_retrieval("documents", len(rows))
        return [
            Evidence(
                source_id=row.source_id,
                source_system=row.source_system,
                source_type=row.source_type,
                title=row.title,
                uri=row.source_uri,
                snippet=row.chunk_text,
                section=row.section_path,
                updated_at=row.source_updated_at.isoformat() if row.source_updated_at else None,
                retrieval_method="vector_postgres",
                scope=Scope(tenant_id=auth.tenant_id, project_id=project_id),
                score=round(max(0.0, 1.0 - float(distance_value)), 4),
                version=row.source_version,
                navigation_target=NavigationTarget(
                    kind="document",
                    entity_id=row.source_id,
                    project_id=project_id,
                    label=f"Open {row.title}",
                ),
            )
            for row, distance_value in rows
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
        vector = self.embedder.embed_query(query)
        distance = TranscriptEmbeddingRow.embedding.cosine_distance(vector)
        statement = (
            select(TranscriptEmbeddingRow, MeetingTranscriptRow, distance.label("distance"))
            .join(
                MeetingTranscriptRow,
                TranscriptEmbeddingRow.transcript_id == MeetingTranscriptRow.id,
            )
            .where(
                TranscriptEmbeddingRow.tenant_id == auth.tenant_id,
                TranscriptEmbeddingRow.project_id == project_id,
                TranscriptEmbeddingRow.acl_principals.op("&&")(list(auth.principals)),
                TranscriptEmbeddingRow.embedding_model == self.embedder.model_id,
                ~TranscriptEmbeddingRow.chunk_text.ilike("Scheduled meeting:%"),
            )
        )
        if meeting_id:
            statement = statement.where(TranscriptEmbeddingRow.meeting_id == meeting_id)
        if date_from:
            statement = statement.where(MeetingTranscriptRow.started_at >= date_from)
        if date_to:
            statement = statement.where(MeetingTranscriptRow.started_at < date_to)
        statement = statement.order_by(distance).limit(top_k)
        with Session(self.engine) as session:
            rows = session.execute(statement).all()
        record_retrieval("transcripts", len(rows))
        return [
            Evidence(
                source_id=str(chunk.id),
                source_system="meeting",
                source_type="transcript",
                title=meeting.title,
                uri=f"lotus://meetings/{chunk.meeting_id}?t={chunk.start_ms}",
                snippet=chunk.chunk_text,
                section=f"{chunk.start_ms}–{chunk.end_ms} ms",
                updated_at=meeting.started_at.isoformat(),
                retrieval_method="vector_postgres",
                scope=Scope(
                    tenant_id=auth.tenant_id,
                    project_id=project_id,
                    meeting_id=chunk.meeting_id,
                ),
                score=round(max(0.0, 1.0 - float(distance_value)), 4),
                meeting_id=chunk.meeting_id,
                start_ms=chunk.start_ms,
                end_ms=chunk.end_ms,
                navigation_target=NavigationTarget(
                    kind="meeting",
                    entity_id=chunk.meeting_id,
                    project_id=project_id,
                    label=f"Open {meeting.title}",
                    timestamp_ms=chunk.start_ms,
                ),
            )
            for chunk, meeting, distance_value in rows
        ]

    def upsert_meeting(
        self,
        meeting_id: str,
        auth: AuthContext,
        transcript: MeetingTranscriptInput,
    ) -> MeetingRecord:
        now = datetime.now(UTC)
        with Session(self.engine) as session:
            row = session.scalar(
                select(MeetingTranscriptRow).where(
                    MeetingTranscriptRow.tenant_id == auth.tenant_id,
                    MeetingTranscriptRow.meeting_id == meeting_id,
                )
            )
            values = {
                "meeting_id": meeting_id,
                "calendar_event_id": transcript.calendar_event_id,
                "tenant_id": auth.tenant_id,
                "project_id": transcript.project_id,
                "team": transcript.team,
                "title": transcript.title,
                "started_at": transcript.started_at,
                "ended_at": transcript.ended_at,
                "participants": transcript.participants,
                "acl_principals": list(auth.principals),
                "language_code": transcript.language_code,
                "recording_url": transcript.recording_url,
                "transcript_json": transcript.model_dump(mode="json"),
                "processing_status": "received",
                "updated_at": now,
            }
            if row is None:
                row = MeetingTranscriptRow(**values)
                session.add(row)
                session.flush()
            else:
                for key, value in values.items():
                    setattr(row, key, value)
            session.execute(
                delete(TranscriptEmbeddingRow).where(
                    TranscriptEmbeddingRow.transcript_id == row.id,
                    TranscriptEmbeddingRow.embedding_model == self.embedder.model_id,
                )
            )
            chunks = chunk_transcript(transcript.segments, target_words=70)
            vectors = self.embedder.embed_documents([chunk.text for chunk in chunks])
            for chunk, vector in zip(chunks, vectors, strict=True):
                session.add(
                    TranscriptEmbeddingRow(
                        transcript_id=row.id,
                        meeting_id=meeting_id,
                        tenant_id=auth.tenant_id,
                        project_id=transcript.project_id,
                        team=transcript.team,
                        chunk_index=chunk.index,
                        chunk_type="transcript",
                        start_ms=chunk.start_ms,
                        end_ms=chunk.end_ms,
                        speakers=list(chunk.speakers),
                        segment_ids=list(chunk.segment_ids),
                        chunk_text=chunk.text,
                        acl_principals=list(auth.principals),
                        content_hash=hashlib.sha256(chunk.text.encode()).hexdigest(),
                        embedding_model=self.embedder.model_id,
                        embedding=vector,
                    )
                )
            session.commit()
        return MeetingRecord(
            meeting_id=meeting_id,
            tenant_id=auth.tenant_id,
            transcript=transcript,
            status="received",
            updated_at=now,
        )

    def _to_record(self, row: MeetingTranscriptRow) -> MeetingRecord:
        stored = row.analysis_json or {}
        if "analysis" in stored:
            analysis_json = stored.get("analysis")
            metadata_json = stored.get("metadata")
        else:
            analysis_json = stored or None
            metadata_json = None
        return MeetingRecord(
            meeting_id=row.meeting_id,
            tenant_id=row.tenant_id,
            transcript=MeetingTranscriptInput.model_validate(row.transcript_json),
            analysis=MeetingAnalysis.model_validate(analysis_json) if analysis_json else None,
            analysis_metadata=(
                MeetingAnalysisMetadata.model_validate(metadata_json) if metadata_json else None
            ),
            status=row.processing_status,
            updated_at=row.updated_at,
        )

    def get_meeting(self, meeting_id: str, auth: AuthContext) -> MeetingRecord | None:
        with Session(self.engine) as session:
            row = session.scalar(
                select(MeetingTranscriptRow).where(
                    MeetingTranscriptRow.tenant_id == auth.tenant_id,
                    MeetingTranscriptRow.meeting_id == meeting_id,
                    MeetingTranscriptRow.acl_principals.op("&&")(list(auth.principals)),
                )
            )
            return self._to_record(row) if row else None

    def save_meeting(self, record: MeetingRecord, auth: AuthContext) -> MeetingRecord:
        with Session(self.engine) as session:
            row = session.scalar(
                select(MeetingTranscriptRow).where(
                    MeetingTranscriptRow.tenant_id == auth.tenant_id,
                    MeetingTranscriptRow.meeting_id == record.meeting_id,
                )
            )
            if row is None:
                raise LookupError(record.meeting_id)
            row.analysis_json = (
                {
                    "analysis": record.analysis.model_dump(mode="json"),
                    "metadata": (
                        record.analysis_metadata.model_dump(mode="json")
                        if record.analysis_metadata
                        else None
                    ),
                }
                if record.analysis
                else None
            )
            row.processing_status = record.status
            row.updated_at = record.updated_at
            session.commit()
        return record

    def list_meetings(
        self,
        auth: AuthContext,
        project_id: str | None = None,
        team: str | None = None,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
    ) -> list[MeetingListItem]:
        statement = select(MeetingTranscriptRow).where(
            MeetingTranscriptRow.tenant_id == auth.tenant_id,
            MeetingTranscriptRow.acl_principals.op("&&")(list(auth.principals)),
        )
        if project_id:
            statement = statement.where(MeetingTranscriptRow.project_id == project_id)
        if team:
            statement = statement.where(MeetingTranscriptRow.team.ilike(team))
        if date_from:
            statement = statement.where(MeetingTranscriptRow.started_at >= date_from)
        if date_to:
            statement = statement.where(MeetingTranscriptRow.started_at < date_to)
        statement = statement.order_by(MeetingTranscriptRow.started_at.desc())
        with Session(self.engine) as session:
            rows = session.scalars(statement).all()
        return [
            MeetingListItem(
                meeting_id=row.meeting_id,
                calendar_event_id=row.calendar_event_id,
                title=row.title,
                project_id=row.project_id,
                team=row.team,
                started_at=row.started_at,
                ended_at=row.ended_at,
                language_code=row.language_code,
                status=row.processing_status,
            )
            for row in rows
        ]

    @staticmethod
    def _calendar_row_to_item(row: CalendarEventRow) -> CalendarEventItem:
        return CalendarEventItem(
            event_id=row.event_id,
            meeting_id=row.meeting_id,
            project_id=row.project_id,
            title=row.title,
            organizer=row.organizer,
            organizer_initials=row.organizer_initials,
            location=row.location,
            description=row.description,
            started_at=row.started_at,
            ended_at=row.ended_at,
            canceled=row.canceled,
            recurring=row.recurring,
        )

    def list_calendar_events(
        self,
        auth: AuthContext,
        project_id: str | None = None,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
    ) -> list[CalendarEventItem]:
        statement = select(CalendarEventRow).where(
            CalendarEventRow.tenant_id == auth.tenant_id,
            CalendarEventRow.acl_principals.op("&&")(list(auth.principals)),
        )
        if project_id:
            statement = statement.where(CalendarEventRow.project_id == project_id)
        if date_from:
            statement = statement.where(CalendarEventRow.started_at >= date_from)
        if date_to:
            statement = statement.where(CalendarEventRow.started_at < date_to)
        statement = statement.order_by(CalendarEventRow.started_at)
        with Session(self.engine) as session:
            rows = session.scalars(statement).all()
        return [self._calendar_row_to_item(row) for row in rows]

    def upsert_calendar_event(
        self,
        auth: AuthContext,
        item: CalendarEventItem,
        acl_principals: list[str] | None = None,
    ) -> CalendarEventItem:
        principals = acl_principals if acl_principals is not None else list(auth.principals)
        now = datetime.now(UTC)
        with Session(self.engine) as session:
            row = session.scalar(
                select(CalendarEventRow).where(
                    CalendarEventRow.tenant_id == auth.tenant_id,
                    CalendarEventRow.event_id == item.event_id,
                )
            )
            values = {
                "event_id": item.event_id,
                "meeting_id": item.meeting_id,
                "tenant_id": auth.tenant_id,
                "project_id": item.project_id,
                "title": item.title,
                "organizer": item.organizer,
                "organizer_initials": item.organizer_initials,
                "location": item.location,
                "description": item.description,
                "started_at": item.started_at,
                "ended_at": item.ended_at,
                "canceled": item.canceled,
                "recurring": item.recurring,
                "acl_principals": principals,
                "updated_at": now,
            }
            if row is None:
                session.add(CalendarEventRow(**values))
            else:
                for key, value in values.items():
                    setattr(row, key, value)
            session.commit()
        return item

    @staticmethod
    def _board_row_to_item(row: BoardIssueRow) -> BoardIssueItem:
        return BoardIssueItem.model_validate(
            {
                "issue_key": row.issue_key,
                "project_id": row.project_id,
                "team_id": row.team_id,
                "title": row.title,
                "issue_type": row.issue_type,
                "feature_key": row.feature_key,
                "feature_title": row.feature_title,
                "description": row.description,
                "acceptance_criteria": row.acceptance_criteria,
                "priority": row.priority,
                "story_points": row.story_points,
                "sprint": row.sprint,
                "reporter_id": row.reporter_id,
                "status": row.status,
                "assignee_id": row.assignee_id,
            }
        )

    def list_board_issues(
        self,
        auth: AuthContext,
        project_id: str | None = None,
        team_id: str | None = None,
    ) -> list[BoardIssueItem]:
        statement = select(BoardIssueRow).where(
            BoardIssueRow.tenant_id == auth.tenant_id,
            BoardIssueRow.acl_principals.op("&&")(list(auth.principals)),
        )
        if project_id:
            statement = statement.where(BoardIssueRow.project_id == project_id)
        if team_id:
            statement = statement.where(BoardIssueRow.team_id == team_id)
        statement = statement.order_by(BoardIssueRow.issue_key)
        with Session(self.engine) as session:
            rows = session.scalars(statement).all()
        return [self._board_row_to_item(row) for row in rows]

    def upsert_board_issue(
        self,
        auth: AuthContext,
        item: BoardIssueItem,
        acl_principals: list[str] | None = None,
    ) -> BoardIssueItem:
        principals = acl_principals if acl_principals is not None else list(auth.principals)
        now = datetime.now(UTC)
        with Session(self.engine) as session:
            row = session.scalar(
                select(BoardIssueRow).where(
                    BoardIssueRow.tenant_id == auth.tenant_id,
                    BoardIssueRow.issue_key == item.issue_key,
                )
            )
            values = {
                "issue_key": item.issue_key,
                "tenant_id": auth.tenant_id,
                "project_id": item.project_id,
                "team_id": item.team_id,
                "title": item.title,
                "issue_type": item.issue_type,
                "feature_key": item.feature_key,
                "feature_title": item.feature_title,
                "description": item.description,
                "acceptance_criteria": item.acceptance_criteria,
                "priority": item.priority,
                "story_points": item.story_points,
                "sprint": item.sprint,
                "reporter_id": item.reporter_id,
                "status": item.status,
                "assignee_id": item.assignee_id,
                "acl_principals": principals,
                "updated_at": now,
            }
            if row is None:
                session.add(BoardIssueRow(**values))
            else:
                for key, value in values.items():
                    setattr(row, key, value)
            session.commit()
        return item

    def update_board_issue(
        self,
        issue_key: str,
        auth: AuthContext,
        patch: BoardIssueUpdate,
    ) -> BoardIssueItem | None:
        with Session(self.engine) as session:
            row = session.scalar(
                select(BoardIssueRow).where(
                    BoardIssueRow.tenant_id == auth.tenant_id,
                    BoardIssueRow.issue_key == issue_key,
                    BoardIssueRow.acl_principals.op("&&")(list(auth.principals)),
                )
            )
            if row is None:
                return None
            updates = patch.model_dump(exclude_unset=True)
            for key, value in updates.items():
                if key == "acceptance_criteria" and value is not None:
                    setattr(row, key, value)
                elif value is not None:
                    setattr(row, key, value)
            row.updated_at = datetime.now(UTC)
            session.commit()
            return self._board_row_to_item(row)

    @staticmethod
    def _document_row_to_dict(row: DocumentEmbeddingRow) -> dict:
        return {
            "chunk_id": row.chunk_id,
            "tenant_id": row.tenant_id,
            "project_id": row.project_id,
            "team": row.team,
            "source_system": row.source_system,
            "source_type": row.source_type,
            "source_id": row.source_id,
            "source_uri": row.source_uri,
            "title": row.title,
            "section_path": row.section_path,
            "chunk_text": row.chunk_text,
            "acl_principals": list(row.acl_principals),
            "metadata_json": dict(row.metadata_json or {}),
            "source_version": row.source_version,
            "source_updated_at": row.source_updated_at,
            "embedding_model": row.embedding_model,
        }

    def list_knowledge_document_chunks(
        self,
        auth: AuthContext,
        project_id: str,
    ) -> list[dict]:
        statement = select(DocumentEmbeddingRow).where(
            DocumentEmbeddingRow.tenant_id == auth.tenant_id,
            DocumentEmbeddingRow.project_id == project_id,
            DocumentEmbeddingRow.acl_principals.op("&&")(list(auth.principals)),
            DocumentEmbeddingRow.embedding_model == self.embedder.model_id,
        )
        with Session(self.engine) as session:
            rows = session.scalars(statement).all()
        return [self._document_row_to_dict(row) for row in rows]

    def upsert_knowledge_document_chunk(
        self,
        auth: AuthContext,
        payload: dict,
    ) -> dict:
        text = payload["chunk_text"]
        vector = self.embedder.embed_documents([text])[0]
        values = {
            **payload,
            "metadata_json": payload.get("metadata") or payload.get("metadata_json") or {},
            "content_hash": hashlib.sha256(text.encode()).hexdigest(),
            "embedding_model": self.embedder.model_id,
            "embedding": vector,
        }
        values.pop("metadata", None)
        with Session(self.engine) as session:
            row = session.scalar(
                select(DocumentEmbeddingRow).where(
                    DocumentEmbeddingRow.tenant_id == auth.tenant_id,
                    DocumentEmbeddingRow.chunk_id == payload["chunk_id"],
                    DocumentEmbeddingRow.embedding_model == self.embedder.model_id,
                )
            )
            if row is None:
                row = DocumentEmbeddingRow(**values)
                session.add(row)
            else:
                for key, value in values.items():
                    setattr(row, key, value)
            session.commit()
            session.refresh(row)
            return self._document_row_to_dict(row)

    @staticmethod
    def _session_summary(row: ChatSessionRow) -> ChatSessionSummary:
        return ChatSessionSummary(
            session_id=row.session_id,
            title=row.title,
            project_id=row.project_id,
            created_at=row.created_at,
            updated_at=row.updated_at,
        )

    @staticmethod
    def _message_record(row: ChatMessageRow, external_session_id: str) -> ChatMessageRecord:
        from ..models import GroundedAnswer

        response = GroundedAnswer.model_validate(row.response_json) if row.response_json else None
        return ChatMessageRecord(
            message_id=row.message_id,
            session_id=external_session_id,
            role=row.role,
            content=row.content,
            execution_id=row.execution_id,
            status=row.status,
            response=response,
            created_at=row.created_at,
        )

    def create_chat_session(
        self, auth: AuthContext, project_id: str, session_id: str | None = None
    ) -> ChatSessionSummary:
        external_id = session_id or str(uuid.uuid4())
        now = datetime.now(UTC)
        with Session(self.engine) as session:
            row = session.scalar(
                select(ChatSessionRow).where(
                    ChatSessionRow.tenant_id == auth.tenant_id,
                    ChatSessionRow.user_id == auth.user_id,
                    ChatSessionRow.session_id == external_id,
                    ChatSessionRow.archived_at.is_(None),
                )
            )
            if row is None:
                row = ChatSessionRow(
                    session_id=external_id,
                    tenant_id=auth.tenant_id,
                    user_id=auth.user_id,
                    project_id=project_id,
                    title="New conversation",
                    created_at=now,
                    updated_at=now,
                )
                session.add(row)
                session.commit()
                session.refresh(row)
            return self._session_summary(row)

    def list_chat_sessions(
        self, auth: AuthContext, limit: int = 30, cursor: str | None = None
    ) -> ChatSessionPage:
        statement = select(ChatSessionRow).where(
            ChatSessionRow.tenant_id == auth.tenant_id,
            ChatSessionRow.user_id == auth.user_id,
            ChatSessionRow.archived_at.is_(None),
        )
        if cursor:
            statement = statement.where(ChatSessionRow.updated_at < datetime.fromisoformat(cursor))
        statement = statement.order_by(ChatSessionRow.updated_at.desc()).limit(limit + 1)
        with Session(self.engine) as session:
            rows = list(session.scalars(statement).all())
        has_more = len(rows) > limit
        rows = rows[:limit]
        return ChatSessionPage(
            items=[self._session_summary(row) for row in rows],
            next_cursor=rows[-1].updated_at.isoformat() if has_more and rows else None,
        )

    def get_chat_session(
        self, session_id: str, auth: AuthContext
    ) -> ChatSessionDetail | None:
        with Session(self.engine) as session:
            row = session.scalar(
                select(ChatSessionRow).where(
                    ChatSessionRow.tenant_id == auth.tenant_id,
                    ChatSessionRow.user_id == auth.user_id,
                    ChatSessionRow.session_id == session_id,
                    ChatSessionRow.archived_at.is_(None),
                )
            )
            if row is None:
                return None
            messages = session.scalars(
                select(ChatMessageRow)
                .where(ChatMessageRow.session_id == row.id)
                .order_by(ChatMessageRow.created_at)
            ).all()
            return ChatSessionDetail(
                session=self._session_summary(row),
                messages=[self._message_record(item, row.session_id) for item in messages],
            )

    def archive_chat_session(self, session_id: str, auth: AuthContext) -> bool:
        with Session(self.engine) as session:
            row = session.scalar(
                select(ChatSessionRow).where(
                    ChatSessionRow.tenant_id == auth.tenant_id,
                    ChatSessionRow.user_id == auth.user_id,
                    ChatSessionRow.session_id == session_id,
                    ChatSessionRow.archived_at.is_(None),
                )
            )
            if row is None:
                return False
            row.archived_at = datetime.now(UTC)
            session.commit()
            return True

    def add_chat_message(
        self,
        session_id: str,
        auth: AuthContext,
        role: str,
        content: str,
        status: str,
        execution_id: str | None = None,
        response: dict | None = None,
    ) -> ChatMessageRecord:
        now = datetime.now(UTC)
        with Session(self.engine) as session:
            parent = session.scalar(
                select(ChatSessionRow).where(
                    ChatSessionRow.tenant_id == auth.tenant_id,
                    ChatSessionRow.user_id == auth.user_id,
                    ChatSessionRow.session_id == session_id,
                    ChatSessionRow.archived_at.is_(None),
                )
            )
            if parent is None:
                raise LookupError(session_id)
            message_count = session.scalar(
                select(func.count()).select_from(ChatMessageRow).where(
                    ChatMessageRow.session_id == parent.id
                )
            )
            if role == "user" and message_count == 0:
                compact = " ".join(content.split())
                parent.title = compact[:77] + ("…" if len(compact) > 77 else "")
            parent.updated_at = now
            row = ChatMessageRow(
                message_id=str(uuid.uuid4()),
                session_id=parent.id,
                role=role,
                content=content,
                execution_id=execution_id,
                status=status,
                response_json=response,
                created_at=now,
            )
            session.add(row)
            session.commit()
            session.refresh(row)
            return self._message_record(row, parent.session_id)

    def update_chat_message_status(
        self, message_id: str, auth: AuthContext, status: str
    ) -> None:
        with Session(self.engine) as session:
            row = session.scalar(
                select(ChatMessageRow)
                .join(ChatSessionRow, ChatMessageRow.session_id == ChatSessionRow.id)
                .where(
                    ChatMessageRow.message_id == message_id,
                    ChatSessionRow.tenant_id == auth.tenant_id,
                    ChatSessionRow.user_id == auth.user_id,
                )
            )
            if row:
                row.status = status
                session.commit()

    def get_chat_context(
        self, session_id: str, auth: AuthContext, limit: int = 12, max_chars: int = 16_000
    ) -> list[ChatMessageRecord]:
        detail = self.get_chat_session(session_id, auth)
        if detail is None:
            return []
        chosen: list[ChatMessageRecord] = []
        used = 0
        for item in reversed(detail.messages):
            if item.status != "completed":
                continue
            size = len(item.content)
            if chosen and used + size > max_chars:
                break
            chosen.append(item)
            used += size
            if len(chosen) >= limit:
                break
        return list(reversed(chosen))

    def get_workspace_project(
        self, project_id: str, auth: AuthContext
    ) -> WorkspaceProject | None:
        with Session(self.engine) as session:
            project = session.scalar(
                select(WorkspaceProjectRow).where(
                    WorkspaceProjectRow.tenant_id == auth.tenant_id,
                    WorkspaceProjectRow.project_id == project_id,
                    WorkspaceProjectRow.acl_principals.op("&&")(list(auth.principals)),
                )
            )
            if project is None:
                return None
            links = session.execute(
                select(ProjectStakeholderRow, EmployeeRow)
                .join(EmployeeRow, ProjectStakeholderRow.employee_id == EmployeeRow.id)
                .where(
                    ProjectStakeholderRow.project_id == project.id,
                    EmployeeRow.acl_principals.op("&&")(list(auth.principals)),
                )
            ).all()
        return WorkspaceProject(
            project_id=project.project_id,
            name=project.name,
            description=project.description,
            status=project.status,
            team=project.team,
            stakeholders=[
                ProjectStakeholder(
                    role=link.role,
                    employee=Employee(
                        employee_id=employee.employee_id,
                        name=employee.name,
                        email=employee.email,
                        designation=employee.designation,
                        team=employee.team,
                        avatar_url=employee.avatar_url,
                        timezone=employee.timezone,
                        contact_handle=employee.contact_handle,
                    ),
                )
                for link, employee in links
            ],
        )

    def search_employees(
        self,
        auth: AuthContext,
        query: str = "",
        team: str | None = None,
        designation: str | None = None,
        timezone: str | None = None,
        limit: int = 20,
    ) -> list[Employee]:
        statement = select(EmployeeRow).where(
            EmployeeRow.tenant_id == auth.tenant_id,
            EmployeeRow.acl_principals.op("&&")(list(auth.principals)),
        )
        normalized = query.strip()
        if normalized:
            pattern = f"%{normalized}%"
            statement = statement.where(
                EmployeeRow.employee_id.ilike(pattern)
                | EmployeeRow.name.ilike(pattern)
                | EmployeeRow.email.ilike(pattern)
                | EmployeeRow.designation.ilike(pattern)
                | EmployeeRow.team.ilike(pattern)
                | EmployeeRow.contact_handle.ilike(pattern)
            )
        if team:
            statement = statement.where(EmployeeRow.team.ilike(team))
        if designation:
            statement = statement.where(EmployeeRow.designation.ilike(f"%{designation}%"))
        if timezone:
            statement = statement.where(EmployeeRow.timezone.ilike(timezone))
        statement = statement.order_by(EmployeeRow.name, EmployeeRow.employee_id).limit(
            min(max(limit, 1), 50)
        )
        with Session(self.engine) as session:
            rows = session.scalars(statement).all()
        return [
            Employee(
                employee_id=row.employee_id,
                name=row.name,
                email=row.email,
                designation=row.designation,
                team=row.team,
                avatar_url=row.avatar_url,
                timezone=row.timezone,
                contact_handle=row.contact_handle,
            )
            for row in rows
        ]
