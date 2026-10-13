"""Create Lotus document and transcript vector stores."""

from alembic import op

from lotus_api.storage.models import Base

revision = "0001_vector_store"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    Base.metadata.create_all(bind=op.get_bind())


def downgrade() -> None:
    bind = op.get_bind()
    for table_name in ("transcript_embeddings", "meeting_transcripts", "document_embeddings"):
        Base.metadata.tables[table_name].drop(bind=bind, checkfirst=True)
