"""Add feature and detail fields to board_issues."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "0004_board_issue_details"
down_revision = "0003_work_board"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "board_issues",
        sa.Column("feature_key", sa.String(length=32), nullable=False, server_default="PROJ-0"),
    )
    op.add_column(
        "board_issues",
        sa.Column("feature_title", sa.Text(), nullable=False, server_default="Linked feature"),
    )
    op.add_column(
        "board_issues",
        sa.Column("description", sa.Text(), nullable=False, server_default=""),
    )
    op.add_column(
        "board_issues",
        sa.Column("acceptance_criteria", JSONB, nullable=False, server_default="[]"),
    )
    op.add_column(
        "board_issues",
        sa.Column("priority", sa.String(length=16), nullable=False, server_default="medium"),
    )
    op.add_column(
        "board_issues",
        sa.Column("story_points", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column("board_issues", sa.Column("sprint", sa.String(length=80), nullable=True))
    op.add_column(
        "board_issues",
        sa.Column(
            "reporter_id",
            sa.String(length=80),
            nullable=False,
            server_default="demo-engineer",
        ),
    )
    op.alter_column("board_issues", "feature_key", server_default=None)
    op.alter_column("board_issues", "feature_title", server_default=None)
    op.alter_column("board_issues", "description", server_default=None)
    op.alter_column("board_issues", "acceptance_criteria", server_default=None)
    op.alter_column("board_issues", "priority", server_default=None)
    op.alter_column("board_issues", "story_points", server_default=None)
    op.alter_column("board_issues", "reporter_id", server_default=None)


def downgrade() -> None:
    for name in (
        "reporter_id",
        "sprint",
        "story_points",
        "priority",
        "acceptance_criteria",
        "description",
        "feature_title",
        "feature_key",
    ):
        op.drop_column("board_issues", name)
