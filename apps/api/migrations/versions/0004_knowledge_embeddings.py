"""Knowledge search with embeddings: fix the vector size, record which embedder made each vector, index it.

Revision ID: 0004
Revises: 0003
"""

import sqlalchemy as sa
from alembic import op

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE knowledge_docs ALTER COLUMN embedding TYPE vector(1024) USING NULL")
    # Vectors from different embedders (Voyage, the local mock) are never compared with each other.
    op.add_column("knowledge_docs", sa.Column("embedding_space", sa.String(40), nullable=True))
    op.execute("CREATE INDEX knowledge_docs_embedding ON knowledge_docs USING hnsw (embedding vector_cosine_ops)")


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS knowledge_docs_embedding")
    op.drop_column("knowledge_docs", "embedding_space")
    op.execute("ALTER TABLE knowledge_docs ALTER COLUMN embedding TYPE vector USING NULL")
