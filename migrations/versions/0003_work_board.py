"""Add board_issues table for Work Board."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision = "0003_work_board"
down_revision = "0002_calendar_events"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "board_issues",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("issue_key", sa.String(length=32), nullable=False),
        sa.Column("tenant_id", sa.String(length=80), nullable=False),
        sa.Column("project_id", sa.String(length=120), nullable=False),
        sa.Column("team_id", sa.String(length=80), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("issue_type", sa.String(length=16), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("assignee_id", sa.String(length=80), nullable=False),
        sa.Column("acl_principals", sa.ARRAY(sa.String()), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("tenant_id", "issue_key"),
    )
    op.create_index(
        "ix_board_scope_team",
        "board_issues",
        ["tenant_id", "project_id", "team_id"],
    )


def downgrade() -> None:
    op.drop_table("board_issues")
