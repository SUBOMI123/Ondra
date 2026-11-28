"""Follow-up sequences: which conversations they apply to, and each customer's place in one.

Revision ID: 0012
Revises: 0011
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0012"
down_revision = "0011"
branch_labels = None
depends_on = None

APP_ROLE = "ondra_app"


def upgrade() -> None:
    op.add_column("follow_up_sequences", sa.Column("active", sa.Boolean, nullable=False, server_default=sa.text("true")))
    # Topics it applies to (ondra_core.routing.TOPICS); empty means any conversation.
    op.add_column("follow_up_sequences", sa.Column("topics", postgresql.ARRAY(sa.Text), nullable=False, server_default=sa.text("'{}'")))
    op.create_table(
        "follow_ups",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False,
                  server_default=sa.text("NULLIF(current_setting('app.tenant_id', true), '')::uuid"), index=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("sequence_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("follow_up_sequences.id", ondelete="CASCADE"), nullable=False),
        sa.Column("conversation_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("contact_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("contacts.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("step", sa.Integer, nullable=False),
        sa.Column("due_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="scheduled"),
        sa.Column("reason", sa.String(60), nullable=True),  # why it ended without sending
        sa.Column("message_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("messages.id", ondelete="SET NULL"), nullable=True),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("status IN ('scheduled', 'awaiting_approval', 'sending', 'sent', 'cancelled', 'needs_person')",
                           name="follow_ups_status"),
    )
    op.execute("ALTER TABLE follow_ups ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE follow_ups FORCE ROW LEVEL SECURITY")
    op.execute("CREATE POLICY tenant_isolation ON follow_ups USING (tenant_id = app_current_tenant()) "
               "WITH CHECK (tenant_id = app_current_tenant())")
    op.execute(f"GRANT SELECT, INSERT, UPDATE, DELETE ON follow_ups TO {APP_ROLE}")


def downgrade() -> None:
    op.drop_table("follow_ups")
    op.drop_column("follow_up_sequences", "topics")
    op.drop_column("follow_up_sequences", "active")
