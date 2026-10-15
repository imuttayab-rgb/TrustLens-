"""Retained messaging, private voice, per-user clear and listing lifecycle.

Additive migration. Application rollback keeps this schema and all evidence.
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql as pg

revision = "202610132130"
down_revision = "202610112000"
branch_labels = None
depends_on = None


def uid(name, target=None, **kw):
    return sa.Column(
        name, pg.UUID(as_uuid=True), *([sa.ForeignKey(target)] if target else []), **kw
    )


def dt(name, **kw):
    return sa.Column(name, sa.DateTime(timezone=True), **kw)


def upgrade():
    for column in [
        sa.Column("edited_body", sa.Text()),
        dt("edited_at"),
        dt("deleted_for_everyone_at"),
        dt("moderated_at"),
        sa.Column("kind", sa.String(10), nullable=False, server_default="text"),
        uid("client_id"),
        uid("reply_to_id", "messages.id"),
        uid("forwarded_from_id", "messages.id"),
        dt("played_at"),
    ]:
        op.add_column("messages", column)
    op.create_index(
        "uq_messages_sender_client", "messages", ["sender_id", "client_id"], unique=True
    )
    op.create_index("ix_messages_cursor", "messages", ["conversation_id", "created_at", "id"])
    op.create_table(
        "chat_lifecycle",
        uid("listing_id", "listings.id", primary_key=True),
        dt("inactive_since"),
        sa.Column("status", sa.String(20), nullable=False),
    )
    op.create_table(
        "chat_clears",
        uid("user_id", "users.id", primary_key=True),
        uid("conversation_id", "conversations.id", primary_key=True),
        dt("cleared_before"),
        dt("previous_before"),
        uid("undo_token"),
        dt("undo_until"),
    )
    op.create_table(
        "chat_voices",
        uid("message_id", "messages.id", primary_key=True),
        sa.Column("bucket", sa.String(100), nullable=False),
        sa.Column("original_key", sa.Text(), nullable=False),
        sa.Column("playback_key", sa.Text(), nullable=False),
        sa.Column("sha256", sa.String(64), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("duration_seconds", sa.Float(), nullable=False),
        sa.Column("waveform", pg.JSONB(), nullable=False),
    )
    op.create_table(
        "chat_versions",
        uid("id", primary_key=True),
        uid("message_id", "messages.id", nullable=False),
        uid("actor_id", "users.id", nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        dt("created_at", nullable=False),
    )
    op.create_index("ix_chat_versions_message", "chat_versions", ["message_id", "created_at"])
    op.create_table(
        "chat_audit",
        uid("id", primary_key=True),
        uid("actor_id", "users.id", nullable=False),
        uid("conversation_id", "conversations.id", nullable=False),
        uid("message_id", "messages.id"),
        sa.Column("action", sa.String(40), nullable=False),
        sa.Column("details", pg.JSONB(), nullable=False),
        dt("created_at", nullable=False),
    )
    op.create_index("ix_chat_audit_conversation", "chat_audit", ["conversation_id", "created_at"])
    op.create_table(
        "chat_cases",
        uid("report_id", "reports.id", primary_key=True),
        uid("conversation_id", "conversations.id", nullable=False),
        uid("message_id", "messages.id"),
        sa.Column("reason", sa.String(30), nullable=False),
    )
    # No reliable historic status-change timestamps exist. Existing inactive
    # listings receive one clearly documented 72-hour grace at installation.
    op.execute(
        "INSERT INTO chat_lifecycle SELECT id, CASE WHEN status::text IN ('ACTIVE','RESERVED') AND deleted_at IS NULL THEN NULL ELSE clock_timestamp() END, CASE WHEN deleted_at IS NOT NULL THEN 'REMOVED' ELSE status::text END FROM listings"
    )
    op.execute("""CREATE FUNCTION chat_track_listing() RETURNS trigger LANGUAGE plpgsql AS $$
    DECLARE active boolean; state text;
    BEGIN
      active := NEW.status::text IN ('ACTIVE','RESERVED') AND NEW.deleted_at IS NULL;
      state := CASE WHEN NEW.deleted_at IS NOT NULL THEN 'REMOVED' ELSE NEW.status::text END;
      INSERT INTO chat_lifecycle(listing_id,inactive_since,status) VALUES(NEW.id,CASE WHEN active THEN NULL ELSE clock_timestamp() END,state)
      ON CONFLICT(listing_id) DO UPDATE SET status=EXCLUDED.status,
        inactive_since=CASE WHEN active THEN NULL ELSE COALESCE(chat_lifecycle.inactive_since,EXCLUDED.inactive_since) END;
      RETURN NEW;
    END $$""")
    op.execute(
        "CREATE TRIGGER chat_listing_lifecycle AFTER INSERT OR UPDATE OF status,deleted_at ON listings FOR EACH ROW EXECUTE FUNCTION chat_track_listing()"
    )
    op.execute("""CREATE FUNCTION chat_retain_record() RETURNS trigger LANGUAGE plpgsql AS $$
    BEGIN RAISE EXCEPTION 'Chat records are retained; permanent deletion is disabled'; END $$""")
    for table in [
        "messages",
        "conversations",
        "chat_voices",
        "chat_versions",
        "chat_audit",
        "chat_cases",
    ]:
        op.execute(
            f"CREATE TRIGGER retain_{table} BEFORE DELETE ON {table} FOR EACH ROW EXECUTE FUNCTION chat_retain_record()"
        )
        op.execute(
            f"CREATE TRIGGER retain_truncate_{table} BEFORE TRUNCATE ON {table} FOR EACH STATEMENT EXECUTE FUNCTION chat_retain_record()"
        )
    for table in ["chat_voices", "chat_versions", "chat_audit", "chat_cases"]:
        op.execute(
            f"CREATE TRIGGER immutable_{table} BEFORE UPDATE ON {table} FOR EACH ROW EXECUTE FUNCTION chat_retain_record()"
        )
    op.execute("""CREATE FUNCTION chat_keep_original() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN
      IF ROW(NEW.id,NEW.body,NEW.sender_id,NEW.conversation_id,NEW.created_at,NEW.kind,NEW.client_id,NEW.reply_to_id,NEW.forwarded_from_id)
         IS DISTINCT FROM ROW(OLD.id,OLD.body,OLD.sender_id,OLD.conversation_id,OLD.created_at,OLD.kind,OLD.client_id,OLD.reply_to_id,OLD.forwarded_from_id)
      THEN RAISE EXCEPTION 'Original message fields are immutable'; END IF;
      RETURN NEW; END $$""")
    op.execute(
        "CREATE TRIGGER immutable_message_original BEFORE UPDATE ON messages FOR EACH ROW EXECUTE FUNCTION chat_keep_original()"
    )


def downgrade():
    raise RuntimeError(
        "Chat evidence must be retained. Roll back application images without downgrading this migration."
    )
