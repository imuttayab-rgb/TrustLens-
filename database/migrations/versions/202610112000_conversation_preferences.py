"""Private, per-participant important conversation markers. Additive only."""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql as pg
revision = '202610112000'
down_revision = '202610110900'
branch_labels = None
depends_on = None

def upgrade():
    op.create_table('conversation_preferences',
        sa.Column('user_id', pg.UUID(as_uuid=True), sa.ForeignKey('users.id'), primary_key=True),
        sa.Column('conversation_id', pg.UUID(as_uuid=True), sa.ForeignKey('conversations.id'), primary_key=True),
        sa.Column('important', sa.Boolean(), nullable=False, server_default=sa.false()))

def downgrade():
    raise RuntimeError('Roll back application images; retain the additive private preference table.')
