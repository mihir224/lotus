"""Add calendar_events table for KnowledgeStore-backed calendar."""

from alembic import op

from lotus_api.storage.models import CalendarEventRow

revision = "0002_calendar_events"
down_revision = "0001_vector_store"
branch_labels = None
depends_on = None


def upgrade() -> None:
    CalendarEventRow.__table__.create(bind=op.get_bind(), checkfirst=True)


def downgrade() -> None:
    op.drop_table("calendar_events")
