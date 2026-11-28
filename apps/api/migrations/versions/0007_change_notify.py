"""Live updates: triggers send a NOTIFY (ids only, never message text) when messages, tasks or conversations change.

Revision ID: 0007
Revises: 0006
"""

from alembic import op

revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None

TABLES = ("messages", "tasks", "conversations")


def upgrade() -> None:
    op.execute(
        """
        CREATE OR REPLACE FUNCTION notify_change() RETURNS trigger LANGUAGE plpgsql AS $$
        DECLARE
          conv uuid;
        BEGIN
          IF TG_TABLE_NAME = 'messages' OR TG_TABLE_NAME = 'tasks' THEN conv := NEW.conversation_id;
          ELSIF TG_TABLE_NAME = 'conversations' THEN conv := NEW.id;
          END IF;
          PERFORM pg_notify('ondra_changes', json_build_object(
            'tenant_id', NEW.tenant_id, 'table', TG_TABLE_NAME, 'id', NEW.id, 'conversation_id', conv
          )::text);
          RETURN NEW;
        END $$
        """
    )
    for t in TABLES:
        op.execute(f"CREATE TRIGGER {t}_notify AFTER INSERT OR UPDATE ON {t} FOR EACH ROW EXECUTE FUNCTION notify_change()")


def downgrade() -> None:
    for t in TABLES:
        op.execute(f"DROP TRIGGER IF EXISTS {t}_notify ON {t}")
    op.execute("DROP FUNCTION IF EXISTS notify_change()")
