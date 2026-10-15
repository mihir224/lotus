"""Create Lotus document and transcript vector stores."""

import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import Vector
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision = "0001_vector_store"
down_revision = None
branch_labels = None
depends_on = None

VECTOR_DIMENSIONS = 768


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.create_table(
        "document_embeddings",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("chunk_id", sa.String(length=160), nullable=False),
        sa.Column("tenant_id", sa.String(length=80), nullable=False),
        sa.Column("project_id", sa.String(length=120), nullable=False),
        sa.Column("team", sa.String(length=120), nullable=False),
        sa.Column("source_system", sa.String(length=40), nullable=False),
        sa.Column("source_type", sa.String(length=40), nullable=False),
        sa.Column("source_id", sa.String(length=160), nullable=False),
        sa.Column("source_uri", sa.Text()),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("section_path", sa.Text()),
        sa.Column("chunk_text", sa.Text(), nullable=False),
        sa.Column("acl_principals", sa.ARRAY(sa.String()), nullable=False),
        sa.Column("metadata_json", JSONB, nullable=False),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column("embedding_model", sa.String(length=160), nullable=False),
        sa.Column("embedding", Vector(VECTOR_DIMENSIONS), nullable=False),
        sa.Column("source_version", sa.String(length=80)),
        sa.Column("source_updated_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("tenant_id", "chunk_id", "embedding_model"),
    )
    op.create_index(
        "ix_document_scope",
        "document_embeddings",
        ["tenant_id", "project_id", "source_type"],
    )
    op.create_index(
        "ix_document_embedding_hnsw",
        "document_embeddings",
        ["embedding"],
        postgresql_using="hnsw",
        postgresql_ops={"embedding": "vector_cosine_ops"},
    )

    op.create_table(
        "meeting_transcripts",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("meeting_id", sa.String(length=120), nullable=False),
        sa.Column("calendar_event_id", sa.String(length=160), nullable=False),
        sa.Column("tenant_id", sa.String(length=80), nullable=False),
        sa.Column("project_id", sa.String(length=120), nullable=False),
        sa.Column("team", sa.String(length=120), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("participants", JSONB, nullable=False),
        sa.Column("acl_principals", sa.ARRAY(sa.String()), nullable=False),
        sa.Column("language_code", sa.String(length=24), nullable=False),
        sa.Column("recording_url", sa.Text()),
        sa.Column("transcript_json", JSONB, nullable=False),
        sa.Column("analysis_json", JSONB),
        sa.Column("processing_status", sa.String(length=32), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("tenant_id", "meeting_id"),
    )
    op.create_index(
        "ix_meeting_scope_date",
        "meeting_transcripts",
        ["tenant_id", "project_id", "started_at"],
    )

    op.create_table(
        "transcript_embeddings",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "transcript_id",
            UUID(as_uuid=True),
            sa.ForeignKey("meeting_transcripts.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("meeting_id", sa.String(length=120), nullable=False),
        sa.Column("tenant_id", sa.String(length=80), nullable=False),
        sa.Column("project_id", sa.String(length=120), nullable=False),
        sa.Column("team", sa.String(length=120), nullable=False),
        sa.Column("chunk_index", sa.Integer(), nullable=False),
        sa.Column("chunk_type", sa.String(length=32), nullable=False),
        sa.Column("start_ms", sa.Integer(), nullable=False),
        sa.Column("end_ms", sa.Integer(), nullable=False),
        sa.Column("speakers", sa.ARRAY(sa.String()), nullable=False),
        sa.Column("segment_ids", sa.ARRAY(sa.String()), nullable=False),
        sa.Column("chunk_text", sa.Text(), nullable=False),
        sa.Column("acl_principals", sa.ARRAY(sa.String()), nullable=False),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column("embedding_model", sa.String(length=160), nullable=False),
        sa.Column("embedding", Vector(VECTOR_DIMENSIONS), nullable=False),
        sa.UniqueConstraint("transcript_id", "chunk_index", "embedding_model"),
    )
    op.create_index(
        "ix_transcript_scope",
        "transcript_embeddings",
        ["tenant_id", "project_id", "meeting_id"],
    )
    op.create_index(
        "ix_transcript_embedding_hnsw",
        "transcript_embeddings",
        ["embedding"],
        postgresql_using="hnsw",
        postgresql_ops={"embedding": "vector_cosine_ops"},
    )


def downgrade() -> None:
    op.drop_table("transcript_embeddings")
    op.drop_table("meeting_transcripts")
    op.drop_table("document_embeddings")
