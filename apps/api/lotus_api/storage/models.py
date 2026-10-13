import uuid
from datetime import datetime
from typing import Any

from pgvector.sqlalchemy import Vector
from sqlalchemy import ARRAY, DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

VECTOR_DIMENSIONS = 768


class Base(DeclarativeBase):
    pass


class DocumentEmbeddingRow(Base):
    __tablename__ = "document_embeddings"
    __table_args__ = (
        UniqueConstraint("tenant_id", "chunk_id", "embedding_model"),
        Index("ix_document_scope", "tenant_id", "project_id", "source_type"),
        Index(
            "ix_document_embedding_hnsw",
            "embedding",
            postgresql_using="hnsw",
            postgresql_ops={"embedding": "vector_cosine_ops"},
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    chunk_id: Mapped[str] = mapped_column(String(160), nullable=False)
    tenant_id: Mapped[str] = mapped_column(String(80), nullable=False)
    project_id: Mapped[str] = mapped_column(String(120), nullable=False)
    team: Mapped[str] = mapped_column(String(120), nullable=False)
    source_system: Mapped[str] = mapped_column(String(40), nullable=False)
    source_type: Mapped[str] = mapped_column(String(40), nullable=False)
    source_id: Mapped[str] = mapped_column(String(160), nullable=False)
    source_uri: Mapped[str | None] = mapped_column(Text)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    section_path: Mapped[str | None] = mapped_column(Text)
    chunk_text: Mapped[str] = mapped_column(Text, nullable=False)
    acl_principals: Mapped[list[str]] = mapped_column(ARRAY(String), nullable=False)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    embedding_model: Mapped[str] = mapped_column(String(160), nullable=False)
    embedding: Mapped[list[float]] = mapped_column(Vector(VECTOR_DIMENSIONS), nullable=False)
    source_version: Mapped[str | None] = mapped_column(String(80))
    source_updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)


class MeetingTranscriptRow(Base):
    __tablename__ = "meeting_transcripts"
    __table_args__ = (
        UniqueConstraint("tenant_id", "meeting_id"),
        Index("ix_meeting_scope_date", "tenant_id", "project_id", "started_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    meeting_id: Mapped[str] = mapped_column(String(120), nullable=False)
    calendar_event_id: Mapped[str] = mapped_column(String(160), nullable=False)
    tenant_id: Mapped[str] = mapped_column(String(80), nullable=False)
    project_id: Mapped[str] = mapped_column(String(120), nullable=False)
    team: Mapped[str] = mapped_column(String(120), nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    ended_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    participants: Mapped[list[str]] = mapped_column(JSONB, nullable=False)
    acl_principals: Mapped[list[str]] = mapped_column(ARRAY(String), nullable=False)
    language_code: Mapped[str] = mapped_column(String(24), nullable=False)
    recording_url: Mapped[str | None] = mapped_column(Text)
    transcript_json: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    analysis_json: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    processing_status: Mapped[str] = mapped_column(String(32), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class TranscriptEmbeddingRow(Base):
    __tablename__ = "transcript_embeddings"
    __table_args__ = (
        UniqueConstraint("transcript_id", "chunk_index", "embedding_model"),
        Index("ix_transcript_scope", "tenant_id", "project_id", "meeting_id"),
        Index(
            "ix_transcript_embedding_hnsw",
            "embedding",
            postgresql_using="hnsw",
            postgresql_ops={"embedding": "vector_cosine_ops"},
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    transcript_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("meeting_transcripts.id", ondelete="CASCADE"), nullable=False
    )
    meeting_id: Mapped[str] = mapped_column(String(120), nullable=False)
    tenant_id: Mapped[str] = mapped_column(String(80), nullable=False)
    project_id: Mapped[str] = mapped_column(String(120), nullable=False)
    team: Mapped[str] = mapped_column(String(120), nullable=False)
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    chunk_type: Mapped[str] = mapped_column(String(32), nullable=False, default="transcript")
    start_ms: Mapped[int] = mapped_column(Integer, nullable=False)
    end_ms: Mapped[int] = mapped_column(Integer, nullable=False)
    speakers: Mapped[list[str]] = mapped_column(ARRAY(String), nullable=False)
    segment_ids: Mapped[list[str]] = mapped_column(ARRAY(String), nullable=False)
    chunk_text: Mapped[str] = mapped_column(Text, nullable=False)
    acl_principals: Mapped[list[str]] = mapped_column(ARRAY(String), nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    embedding_model: Mapped[str] = mapped_column(String(160), nullable=False)
    embedding: Mapped[list[float]] = mapped_column(Vector(VECTOR_DIMENSIONS), nullable=False)
