"""Add typed category metadata and opt-in phone visibility; legacy data untouched."""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql as pg
revision = '202610110900'
down_revision = '202610050900'
branch_labels = None
depends_on = None

def upgrade():
    op.create_table('private_account_settings',
        sa.Column('user_id', pg.UUID(as_uuid=True), sa.ForeignKey('users.id'), primary_key=True),
        sa.Column('date_of_birth', sa.String(10), nullable=True),
        sa.Column('gender', sa.String(40), nullable=True),
        sa.Column('addresses', pg.JSONB(), nullable=False, server_default='[]'),
        sa.Column('version', sa.Integer(), nullable=False, server_default='1'))
    op.create_table('account_deletion_requests',
        sa.Column('user_id', pg.UUID(as_uuid=True), sa.ForeignKey('users.id'), primary_key=True),
        sa.Column('status', sa.String(40), nullable=False, server_default='PENDING_REVIEW'),
        sa.Column('requested_at', sa.DateTime(timezone=True), nullable=False))
    op.add_column('saved_searches', sa.Column('category_node_id', sa.String(240), nullable=True))
    op.add_column('saved_searches', sa.Column('facets', pg.JSONB(), nullable=False, server_default='{}'))
    op.add_column('listing_images', sa.Column('is_removed', sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column('listings', sa.Column('category_node_id', sa.String(240), nullable=True))
    op.add_column('listings', sa.Column('category_schema_version', sa.Integer(), nullable=True))
    op.add_column('listings', sa.Column('category_data', pg.JSONB(), nullable=False, server_default='{}'))
    op.add_column('listings', sa.Column('show_phone', sa.Boolean(), nullable=False, server_default=sa.false()))
    op.create_index('ix_listings_category_node_id', 'listings', ['category_node_id'])
    op.create_index('ix_listings_category_data', 'listings', ['category_data'], postgresql_using='gin')

def downgrade():
    raise RuntimeError('Roll back application images; retain additive category data. Do not drop user data.')
