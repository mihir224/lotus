"""Add board_issues table for Work Board."""

from alembic import op

from lotus_api.storage.models import BoardIssueRow

revision = "0003_work_board"
down_revision = "0002_calendar_events"
branch_labels = None
depends_on = None


def upgrade() -> None:
    BoardIssueRow.__table__.create(bind=op.get_bind(), checkfirst=True)


def downgrade() -> None:
    op.drop_table("board_issues")
