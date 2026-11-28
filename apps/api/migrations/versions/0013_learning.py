"""Learning loop: ratings on Ondra's replies, and unanswered questions that group by meaning.

Revision ID: 0013
Revises: 0012
"""

import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import Vector
from sqlalchemy.dialects import postgresql

revision = "0013"
down_revision = "0012"
branch_labels = None
depends_on = None

APP_ROLE = "ondra_app"


def upgrade() -> None:
    # The same question asked in different words is one gap: compared by embedding, like knowledge search.
    op.add_column("knowledge_gaps", sa.Column("embedding", Vector(1024), nullable=True))
    op.add_column("knowledge_gaps", sa.Column("embedding_space", sa.String(40), nullable=True))
    op.add_column("knowledge_gaps", sa.Column("last_asked_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False))
    op.create_table(
        "message_ratings",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False,
                  server_default=sa.text("NULLIF(current_setting('app.tenant_id', true), '')::uuid"), index=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("message_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("messages.id", ondelete="CASCADE"), nullable=False, unique=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("rating", sa.String(10), nullable=False),
        sa.Column("note", sa.Text, nullable=True),
        sa.CheckConstraint("rating IN ('good', 'wrong', 'tone')", name="message_ratings_rating"),
    )
    op.execute("ALTER TABLE message_ratings ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE message_ratings FORCE ROW LEVEL SECURITY")
    op.execute("CREATE POLICY tenant_isolation ON message_ratings USING (tenant_id = app_current_tenant()) "
               "WITH CHECK (tenant_id = app_current_tenant())")
    op.execute(f"GRANT SELECT, INSERT, UPDATE, DELETE ON message_ratings TO {APP_ROLE}")


def downgrade() -> None:
    op.drop_table("message_ratings")
    for c in ("last_asked_at", "embedding_space", "embedding"):
        op.drop_column("knowledge_gaps", c)
