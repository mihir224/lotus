"""Add persistent conversations and workspace directory data."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID

revision = "0005_conversations_workspace"
down_revision = "0004_board_issue_details"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "chat_sessions",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("session_id", sa.String(128), nullable=False),
        sa.Column("tenant_id", sa.String(80), nullable=False),
        sa.Column("user_id", sa.String(160), nullable=False),
        sa.Column("project_id", sa.String(120), nullable=False),
        sa.Column("title", sa.String(240), nullable=False),
        sa.Column("archived_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("tenant_id", "user_id", "session_id"),
    )
    op.create_index(
        "ix_chat_session_owner_updated",
        "chat_sessions",
        ["tenant_id", "user_id", "updated_at"],
    )
    op.create_table(
        "chat_messages",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("message_id", sa.String(128), nullable=False),
        sa.Column(
            "session_id",
            UUID(as_uuid=True),
            sa.ForeignKey("chat_sessions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("role", sa.String(16), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("execution_id", sa.String(64)),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("response_json", JSONB),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("session_id", "message_id"),
    )
    op.create_index(
        "ix_chat_message_session_created", "chat_messages", ["session_id", "created_at"]
    )
    op.create_table(
        "workspace_projects",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", sa.String(80), nullable=False),
        sa.Column("project_id", sa.String(120), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("status", sa.String(40), nullable=False),
        sa.Column("team", sa.String(120), nullable=False),
        sa.Column("acl_principals", ARRAY(sa.String()), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("tenant_id", "project_id"),
    )
    op.create_table(
        "employees",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", sa.String(80), nullable=False),
        sa.Column("employee_id", sa.String(120), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("email", sa.String(320), nullable=False),
        sa.Column("designation", sa.String(200), nullable=False),
        sa.Column("team", sa.String(120), nullable=False),
        sa.Column("avatar_url", sa.Text()),
        sa.Column("timezone", sa.String(80), nullable=False),
        sa.Column("contact_handle", sa.String(160), nullable=False),
        sa.Column("acl_principals", ARRAY(sa.String()), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("tenant_id", "employee_id"),
    )
    op.create_table(
        "project_stakeholders",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "project_id",
            UUID(as_uuid=True),
            sa.ForeignKey("workspace_projects.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "employee_id",
            UUID(as_uuid=True),
            sa.ForeignKey("employees.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("role", sa.String(120), nullable=False),
        sa.UniqueConstraint("project_id", "employee_id", "role"),
    )


def downgrade() -> None:
    op.drop_table("project_stakeholders")
    op.drop_table("employees")
    op.drop_table("workspace_projects")
    op.drop_index("ix_chat_message_session_created", table_name="chat_messages")
    op.drop_table("chat_messages")
    op.drop_index("ix_chat_session_owner_updated", table_name="chat_sessions")
    op.drop_table("chat_sessions")
