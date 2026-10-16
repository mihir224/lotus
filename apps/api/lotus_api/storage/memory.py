import hashlib
import json
import math
import uuid
from datetime import UTC, datetime
from typing import Any

from ..chunking import chunk_transcript
from ..config import Settings
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
    MeetingListItem,
    MeetingRecord,
    MeetingTranscriptInput,
    NavigationTarget,
    ProjectStakeholder,
    Scope,
    WorkspaceProject,
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
        self.calendar_events: dict[str, dict[str, Any]] = {}
        self.board_issues: dict[str, dict[str, Any]] = {}
        self.chat_sessions: dict[str, dict[str, Any]] = {}
        self.projects: dict[str, WorkspaceProject] = {}
        self.employees: dict[str, dict[str, Any]] = {}
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
            self.calendar_events[item.event_id] = {
                "item": item,
                "tenant_id": payload["tenant_id"],
                "acl_principals": payload.get("acl_principals", ["group:demo"]),
            }

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
        self.employees = {
            row["employee_id"]: {
                "employee": Employee.model_validate(
                {
                    key: value
                    for key, value in row.items()
                    if key not in {"tenant_id", "acl_principals"}
                }),
                "tenant_id": row["tenant_id"],
                "acl_principals": row.get("acl_principals", ["group:demo"]),
            }
            for row in self._load("enterprise/employees.json")
        }
        for row in self._load("enterprise/projects.json"):
            self.projects[row["project_id"]] = WorkspaceProject(
                project_id=row["project_id"],
                name=row["name"],
                description=row["description"],
                status=row["status"],
                team=row["team"],
                stakeholders=[
                    ProjectStakeholder(
                        role=link["role"],
                        employee=self.employees[link["employee_id"]]["employee"],
                    )
                    for link in row.get("stakeholders", [])
                    if link["employee_id"] in self.employees
                ],
            )
        return {
            "documents": len(self.documents),
            "meetings": len(self.meetings),
            "calendar_events": len(calendar_rows),
            "board_issues": len(board_rows),
            "employees": len(self.employees),
            "projects": len(self.projects),
        }

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
            if score >= 0.25 or exact_source:
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
                updated_at=(
                    row["source_updated_at"].isoformat()
                    if isinstance(row.get("source_updated_at"), datetime)
                    else row.get("source_updated_at")
                ),
                retrieval_method="vector_fixture",
                scope=Scope(tenant_id=auth.tenant_id, project_id=project_id),
                score=round(score, 4),
                version=row.get("source_version"),
                navigation_target=NavigationTarget(
                    kind="document",
                    entity_id=row["source_id"],
                    project_id=project_id,
                    label=f"Open {row['title']}",
                ),
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
                if row["chunk_text"].strip().casefold().startswith("scheduled meeting:"):
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
                navigation_target=NavigationTarget(
                    kind="meeting",
                    entity_id=row["meeting_id"],
                    project_id=project_id,
                    label=f"Open {row['title']}",
                    timestamp_ms=row["start_ms"],
                ),
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

    def _calendar_authorized(self, row: dict[str, Any], auth: AuthContext) -> bool:
        if row["tenant_id"] != auth.tenant_id:
            return False
        principals = row.get("acl_principals", [])
        if not isinstance(principals, list):
            return False
        return bool(set(principals) & set(auth.principals))

    def list_calendar_events(
        self,
        auth: AuthContext,
        project_id: str | None = None,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
    ) -> list[CalendarEventItem]:
        result: list[CalendarEventItem] = []
        for row in self.calendar_events.values():
            if not self._calendar_authorized(row, auth):
                continue
            item: CalendarEventItem = row["item"]
            if project_id and item.project_id != project_id:
                continue
            if date_from and item.started_at < date_from:
                continue
            if date_to and item.started_at >= date_to:
                continue
            result.append(item)
        return sorted(result, key=lambda row: row.started_at)

    def upsert_calendar_event(
        self,
        auth: AuthContext,
        item: CalendarEventItem,
        acl_principals: list[str] | None = None,
    ) -> CalendarEventItem:
        principals = acl_principals if acl_principals is not None else list(auth.principals)
        self.calendar_events[item.event_id] = {
            "item": item,
            "tenant_id": auth.tenant_id,
            "acl_principals": principals,
        }
        return item

    def list_board_issues(
        self,
        auth: AuthContext,
        project_id: str | None = None,
        team_id: str | None = None,
    ) -> list[BoardIssueItem]:
        result: list[BoardIssueItem] = []
        for row in self.board_issues.values():
            if not self._calendar_authorized(row, auth):
                continue
            item: BoardIssueItem = row["item"]
            if project_id and item.project_id != project_id:
                continue
            if team_id and item.team_id != team_id:
                continue
            result.append(item)
        return sorted(result, key=lambda row: row.issue_key)

    def upsert_board_issue(
        self,
        auth: AuthContext,
        item: BoardIssueItem,
        acl_principals: list[str] | None = None,
    ) -> BoardIssueItem:
        principals = acl_principals if acl_principals is not None else list(auth.principals)
        self.board_issues[item.issue_key] = {
            "item": item,
            "tenant_id": auth.tenant_id,
            "acl_principals": principals,
        }
        return item

    def update_board_issue(
        self,
        issue_key: str,
        auth: AuthContext,
        patch: BoardIssueUpdate,
    ) -> BoardIssueItem | None:
        row = self.board_issues.get(issue_key)
        if row is None or not self._calendar_authorized(row, auth):
            return None
        current: BoardIssueItem = row["item"]
        updates = patch.model_dump(exclude_unset=True)
        filtered = {
            key: value
            for key, value in updates.items()
            if key == "acceptance_criteria" or value is not None
        }
        updated = current.model_copy(update=filtered)
        row["item"] = updated
        return updated

    def list_knowledge_document_chunks(
        self,
        auth: AuthContext,
        project_id: str,
    ) -> list[dict]:
        rows: list[dict] = []
        for row in self.documents.values():
            if not _allowed(row, auth, project_id):
                continue
            if row.get("embedding_model") != self.embedder.model_id:
                continue
            rows.append(dict(row))
        return rows

    def upsert_knowledge_document_chunk(
        self,
        auth: AuthContext,
        payload: dict,
    ) -> dict:
        row = dict(payload)
        text = row["chunk_text"]
        row["embedding_model"] = self.embedder.model_id
        row["embedding"] = self.embedder.embed_documents([text])[0]
        row["content_hash"] = hashlib.sha256(text.encode()).hexdigest()
        if "metadata" in row:
            row.setdefault("metadata_json", row.pop("metadata"))
        row["acl_principals"] = list(row.get("acl_principals") or auth.principals)
        self.documents[row["chunk_id"]] = row
        return row

    def delete_knowledge_document_source(
        self,
        auth: AuthContext,
        project_id: str,
        source_id: str,
    ) -> bool:
        chunk_ids = [
            chunk_id
            for chunk_id, row in self.documents.items()
            if row.get("source_id") == source_id and _allowed(row, auth, project_id)
        ]
        for chunk_id in chunk_ids:
            del self.documents[chunk_id]
        return bool(chunk_ids)

    def create_chat_session(
        self, auth: AuthContext, project_id: str, session_id: str | None = None
    ) -> ChatSessionSummary:
        external_id = session_id or str(uuid.uuid4())
        existing = self.chat_sessions.get(external_id)
        if (
            existing
            and existing["tenant_id"] == auth.tenant_id
            and existing["user_id"] == auth.user_id
        ):
            return existing["summary"]
        now = datetime.now(UTC)
        summary = ChatSessionSummary(
            session_id=external_id,
            title="New conversation",
            project_id=project_id,
            created_at=now,
            updated_at=now,
        )
        self.chat_sessions[external_id] = {
            "tenant_id": auth.tenant_id,
            "user_id": auth.user_id,
            "summary": summary,
            "messages": [],
            "archived": False,
        }
        return summary

    def _owned_chat(self, session_id: str, auth: AuthContext) -> dict[str, Any] | None:
        row = self.chat_sessions.get(session_id)
        if (
            not row
            or row["tenant_id"] != auth.tenant_id
            or row["user_id"] != auth.user_id
            or row["archived"]
        ):
            return None
        return row

    def list_chat_sessions(
        self, auth: AuthContext, limit: int = 30, cursor: str | None = None
    ) -> ChatSessionPage:
        rows = [
            row["summary"]
            for row in self.chat_sessions.values()
            if row["tenant_id"] == auth.tenant_id
            and row["user_id"] == auth.user_id
            and not row["archived"]
        ]
        rows.sort(key=lambda item: item.updated_at, reverse=True)
        if cursor:
            cutoff = datetime.fromisoformat(cursor)
            rows = [row for row in rows if row.updated_at < cutoff]
        has_more = len(rows) > limit
        rows = rows[:limit]
        return ChatSessionPage(
            items=rows,
            next_cursor=rows[-1].updated_at.isoformat() if has_more and rows else None,
        )

    def get_chat_session(
        self, session_id: str, auth: AuthContext
    ) -> ChatSessionDetail | None:
        row = self._owned_chat(session_id, auth)
        if row is None:
            return None
        return ChatSessionDetail(session=row["summary"], messages=list(row["messages"]))

    def archive_chat_session(self, session_id: str, auth: AuthContext) -> bool:
        row = self._owned_chat(session_id, auth)
        if row is None:
            return False
        row["archived"] = True
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
        from ..models import GroundedAnswer

        row = self._owned_chat(session_id, auth)
        if row is None:
            raise LookupError(session_id)
        now = datetime.now(UTC)
        if role == "user" and not row["messages"]:
            compact = " ".join(content.split())
            row["summary"] = row["summary"].model_copy(
                update={"title": compact[:77] + ("…" if len(compact) > 77 else "")}
            )
        row["summary"] = row["summary"].model_copy(update={"updated_at": now})
        message = ChatMessageRecord(
            message_id=str(uuid.uuid4()),
            session_id=session_id,
            role=role,
            content=content,
            execution_id=execution_id,
            status=status,
            response=GroundedAnswer.model_validate(response) if response else None,
            created_at=now,
        )
        row["messages"].append(message)
        return message

    def update_chat_message_status(
        self, message_id: str, auth: AuthContext, status: str
    ) -> None:
        for row in self.chat_sessions.values():
            if row["tenant_id"] != auth.tenant_id or row["user_id"] != auth.user_id:
                continue
            row["messages"] = [
                item.model_copy(update={"status": status})
                if item.message_id == message_id
                else item
                for item in row["messages"]
            ]

    def get_chat_context(
        self, session_id: str, auth: AuthContext, limit: int = 12, max_chars: int = 16_000
    ) -> list[ChatMessageRecord]:
        detail = self.get_chat_session(session_id, auth)
        if detail is None:
            return []
        result: list[ChatMessageRecord] = []
        used = 0
        for item in reversed(detail.messages):
            if item.status != "completed":
                continue
            if result and used + len(item.content) > max_chars:
                break
            result.append(item)
            used += len(item.content)
            if len(result) >= limit:
                break
        return list(reversed(result))

    def get_workspace_project(
        self, project_id: str, auth: AuthContext
    ) -> WorkspaceProject | None:
        if auth.tenant_id != "demo" or "group:demo" not in auth.principals:
            return None
        return self.projects.get(project_id)

    def search_employees(
        self,
        auth: AuthContext,
        query: str = "",
        team: str | None = None,
        designation: str | None = None,
        timezone: str | None = None,
        limit: int = 20,
    ) -> list[Employee]:
        normalized = query.strip().casefold()
        matches: list[Employee] = []
        for payload in self.employees.values():
            if payload["tenant_id"] != auth.tenant_id:
                continue
            if not set(payload["acl_principals"]) & set(auth.principals):
                continue
            employee = payload["employee"]
            if team and employee.team.casefold() != team.casefold():
                continue
            if designation and designation.casefold() not in employee.designation.casefold():
                continue
            if timezone and employee.timezone.casefold() != timezone.casefold():
                continue
            searchable = (
                f"{employee.employee_id} {employee.name} {employee.email} "
                f"{employee.designation} {employee.team} {employee.contact_handle}"
            ).casefold()
            if normalized and normalized not in searchable:
                continue
            matches.append(employee)
        matches.sort(key=lambda employee: (employee.name.casefold(), employee.employee_id))
        return matches[: min(max(limit, 1), 50)]
