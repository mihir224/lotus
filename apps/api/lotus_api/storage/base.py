from collections.abc import Sequence
from datetime import datetime
from typing import Protocol

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
    MeetingListItem,
    MeetingRecord,
    MeetingTranscriptInput,
    WorkspaceProject,
)


class KnowledgeStore(Protocol):
    def ready(self) -> bool: ...

    def seed(self) -> dict[str, int]: ...

    def search_documents(
        self,
        query: str,
        auth: AuthContext,
        project_id: str,
        top_k: int = 8,
        source_types: Sequence[str] = (),
    ) -> list[Evidence]: ...

    def search_transcripts(
        self,
        query: str,
        auth: AuthContext,
        project_id: str,
        top_k: int = 8,
        meeting_id: str | None = None,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
    ) -> list[Evidence]: ...

    def upsert_meeting(
        self,
        meeting_id: str,
        auth: AuthContext,
        transcript: MeetingTranscriptInput,
    ) -> MeetingRecord: ...

    def get_meeting(self, meeting_id: str, auth: AuthContext) -> MeetingRecord | None: ...

    def save_meeting(self, record: MeetingRecord, auth: AuthContext) -> MeetingRecord: ...

    def list_meetings(
        self,
        auth: AuthContext,
        project_id: str | None = None,
        team: str | None = None,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
    ) -> list[MeetingListItem]: ...

    def list_calendar_events(
        self,
        auth: AuthContext,
        project_id: str | None = None,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
    ) -> list[CalendarEventItem]: ...

    def upsert_calendar_event(
        self,
        auth: AuthContext,
        item: CalendarEventItem,
        acl_principals: list[str] | None = None,
    ) -> CalendarEventItem: ...

    def list_board_issues(
        self,
        auth: AuthContext,
        project_id: str | None = None,
        team_id: str | None = None,
    ) -> list[BoardIssueItem]: ...

    def update_board_issue(
        self,
        issue_key: str,
        auth: AuthContext,
        patch: BoardIssueUpdate,
    ) -> BoardIssueItem | None: ...

    def upsert_board_issue(
        self,
        auth: AuthContext,
        item: BoardIssueItem,
        acl_principals: list[str] | None = None,
    ) -> BoardIssueItem: ...

    def list_knowledge_document_chunks(
        self,
        auth: AuthContext,
        project_id: str,
    ) -> list[dict]: ...

    def upsert_knowledge_document_chunk(
        self,
        auth: AuthContext,
        payload: dict,
    ) -> dict: ...

    def delete_knowledge_document_source(
        self,
        auth: AuthContext,
        project_id: str,
        source_id: str,
    ) -> bool: ...

    def create_chat_session(
        self, auth: AuthContext, project_id: str, session_id: str | None = None
    ) -> ChatSessionSummary: ...

    def list_chat_sessions(
        self, auth: AuthContext, limit: int = 30, cursor: str | None = None
    ) -> ChatSessionPage: ...

    def get_chat_session(
        self, session_id: str, auth: AuthContext
    ) -> ChatSessionDetail | None: ...

    def archive_chat_session(self, session_id: str, auth: AuthContext) -> bool: ...

    def add_chat_message(
        self,
        session_id: str,
        auth: AuthContext,
        role: str,
        content: str,
        status: str,
        execution_id: str | None = None,
        response: dict | None = None,
    ) -> ChatMessageRecord: ...

    def update_chat_message_status(
        self, message_id: str, auth: AuthContext, status: str
    ) -> None: ...

    def get_chat_context(
        self, session_id: str, auth: AuthContext, limit: int = 12, max_chars: int = 16_000
    ) -> list[ChatMessageRecord]: ...

    def get_workspace_project(
        self, project_id: str, auth: AuthContext
    ) -> WorkspaceProject | None: ...

    def search_employees(
        self,
        auth: AuthContext,
        query: str = "",
        team: str | None = None,
        designation: str | None = None,
        timezone: str | None = None,
        limit: int = 20,
    ) -> list[Employee]: ...
