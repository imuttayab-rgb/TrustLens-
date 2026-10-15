"""Retained in-platform voice-call metadata and encrypted push subscriptions."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql as pg

revision = "202610140100"
down_revision = "202610132130"
branch_labels = None
depends_on = None


def upgrade():
    def uid(name, target=None, **kw):
        return sa.Column(
            name, pg.UUID(as_uuid=True), *([sa.ForeignKey(target)] if target else []), **kw
        )

    def dt(name, **kw):
        return sa.Column(name, sa.DateTime(timezone=True), **kw)

    op.create_table(
        "chat_calls",
        uid("id", primary_key=True),
        uid("conversation_id", "conversations.id", nullable=False),
        uid("caller_id", "users.id", nullable=False),
        uid("callee_id", "users.id", nullable=False),
        uid("caller_device", nullable=False),
        uid("callee_device"),
        sa.Column("state", sa.String(15), nullable=False),
        sa.Column("reason", sa.String(30)),
        dt("created_at", nullable=False),
        dt("accepted_at"),
        dt("connected_at"),
        dt("ended_at"),
        dt("caller_seen_at", nullable=False),
        dt("callee_seen_at"),
        sa.Column("caller_connected", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("callee_connected", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("caller_muted", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("callee_muted", sa.Boolean(), nullable=False, server_default="false"),
        sa.CheckConstraint("caller_id <> callee_id", name="call_distinct_participants"),
        sa.CheckConstraint(
            "state IN ('calling','ringing','connecting','active','ended')", name="call_state"
        ),
    )
    op.create_table(
        "chat_call_runtime",
        uid("call_id", "chat_calls.id", primary_key=True),
        sa.Column("push_attempted", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("room_closed", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("caller_health", pg.JSONB(), nullable=False, server_default="{}"),
        sa.Column("callee_health", pg.JSONB(), nullable=False, server_default="{}"),
    )
    op.create_table(
        "chat_push_subscriptions",
        uid("id", primary_key=True),
        uid("user_id", "users.id", nullable=False),
        sa.Column("endpoint_hash", sa.String(64), nullable=False, unique=True),
        sa.Column("encrypted_subscription", sa.Text(), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default="true"),
        dt("created_at", nullable=False),
    )
    op.create_index("ix_chat_push_user", "chat_push_subscriptions", ["user_id", "enabled"])
    for side in ["caller", "callee"]:
        op.create_index(f"ix_chat_calls_{side}_state", "chat_calls", [f"{side}_id", "state"])
    op.create_index("ix_chat_calls_history", "chat_calls", ["conversation_id", "created_at"])
    op.execute(
        "CREATE TRIGGER retain_chat_calls BEFORE DELETE ON chat_calls FOR EACH ROW EXECUTE FUNCTION chat_retain_record()"
    )
    op.execute(
        "CREATE TRIGGER retain_truncate_chat_calls BEFORE TRUNCATE ON chat_calls FOR EACH STATEMENT EXECUTE FUNCTION chat_retain_record()"
    )
    op.execute("""CREATE FUNCTION chat_call_keep_record() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN
      IF OLD.state = 'ended' OR ROW(NEW.id,NEW.conversation_id,NEW.caller_id,NEW.callee_id,NEW.caller_device,NEW.created_at)
        IS DISTINCT FROM ROW(OLD.id,OLD.conversation_id,OLD.caller_id,OLD.callee_id,OLD.caller_device,OLD.created_at)
      THEN RAISE EXCEPTION 'Call records are retained and completed calls are immutable'; END IF;
      RETURN NEW; END $$""")
    op.execute(
        "CREATE TRIGGER immutable_chat_call BEFORE UPDATE ON chat_calls FOR EACH ROW EXECUTE FUNCTION chat_call_keep_record()"
    )


def downgrade():
    raise RuntimeError("Call records are retained; do not downgrade this migration.")
