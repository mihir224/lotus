"""Add calendar_events table for KnowledgeStore-backed calendar."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision = "0002_calendar_events"
down_revision = "0001_vector_store"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "calendar_events",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("event_id", sa.String(length=160), nullable=False),
        sa.Column("meeting_id", sa.String(length=120), nullable=False),
        sa.Column("tenant_id", sa.String(length=80), nullable=False),
        sa.Column("project_id", sa.String(length=120), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("organizer", sa.String(length=160), nullable=False),
        sa.Column("organizer_initials", sa.String(length=8), nullable=False),
        sa.Column("location", sa.Text()),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("canceled", sa.Boolean(), nullable=False),
        sa.Column("recurring", sa.Boolean(), nullable=False),
        sa.Column("acl_principals", sa.ARRAY(sa.String()), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("tenant_id", "event_id"),
    )
    op.create_index(
        "ix_calendar_scope_date",
        "calendar_events",
        ["tenant_id", "project_id", "started_at"],
    )


def downgrade() -> None:
    op.drop_table("calendar_events")
