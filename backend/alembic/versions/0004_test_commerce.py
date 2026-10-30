"""Isolated test commerce schema, frozen at release creation."""
from alembic import op
import sqlalchemy as sa

revision = "0004_test_commerce"
down_revision = "0003_local_delivery_places"
branch_labels = None
depends_on = None

def upgrade():
    op.create_table('commerce_audit_events',
        sa.Column('id', sa.BigInteger().with_variant(sa.Integer(), "sqlite"), nullable=False, primary_key=True),
        sa.Column('store_id', sa.BigInteger().with_variant(sa.Integer(), "sqlite"), sa.ForeignKey('stores.id'), nullable=False, primary_key=False),
        sa.Column('actor', sa.String(80), nullable=False, primary_key=False),
        sa.Column('action', sa.String(80), nullable=False, primary_key=False),
        sa.Column('subject', sa.String(100), nullable=False, primary_key=False),
        sa.Column('detail', sa.JSON(), nullable=False, primary_key=False),
        sa.Column('created_at', sa.DateTime(), nullable=False, primary_key=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column('updated_at', sa.DateTime(), nullable=False, primary_key=False, server_default=sa.text("CURRENT_TIMESTAMP")),
    )
    op.create_index('ix_commerce_audit_events_store_id', 'commerce_audit_events', ['store_id'], unique=False)
    op.create_table('commerce_coupons',
        sa.Column('id', sa.BigInteger().with_variant(sa.Integer(), "sqlite"), nullable=False, primary_key=True),
        sa.Column('store_id', sa.BigInteger().with_variant(sa.Integer(), "sqlite"), sa.ForeignKey('stores.id'), nullable=False, primary_key=False),
        sa.Column('title', sa.String(100), nullable=False, primary_key=False),
        sa.Column('amount_cents', sa.Integer(), nullable=False, primary_key=False),
        sa.Column('minimum_cents', sa.Integer(), nullable=False, primary_key=False),
        sa.Column('quantity', sa.Integer(), nullable=False, primary_key=False),
        sa.Column('starts_at', sa.DateTime(), nullable=False, primary_key=False),
        sa.Column('expires_at', sa.DateTime(), nullable=False, primary_key=False),
        sa.Column('birthday_only', sa.Boolean(), nullable=False, primary_key=False),
        sa.Column('enabled', sa.Boolean(), nullable=False, primary_key=False),
        sa.Column('created_at', sa.DateTime(), nullable=False, primary_key=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column('updated_at', sa.DateTime(), nullable=False, primary_key=False, server_default=sa.text("CURRENT_TIMESTAMP")),
    )
    op.create_index('ix_commerce_coupons_store_id', 'commerce_coupons', ['store_id'], unique=False)
    op.create_table('commerce_members',
        sa.Column('id', sa.BigInteger().with_variant(sa.Integer(), "sqlite"), nullable=False, primary_key=True),
        sa.Column('store_id', sa.BigInteger().with_variant(sa.Integer(), "sqlite"), sa.ForeignKey('stores.id'), nullable=False, primary_key=False),
        sa.Column('phone', sa.String(20), nullable=False, primary_key=False),
        sa.Column('password_hash', sa.String(500), nullable=False, primary_key=False),
        sa.Column('name', sa.String(60), nullable=False, primary_key=False),
        sa.Column('birthday', sa.String(10), nullable=True, primary_key=False),
        sa.Column('points', sa.Integer(), nullable=False, primary_key=False),
        sa.Column('wallet_cents', sa.Integer(), nullable=False, primary_key=False),
        sa.Column('lifetime_cents', sa.BigInteger().with_variant(sa.Integer(), "sqlite"), nullable=False, primary_key=False),
        sa.Column('enabled', sa.Boolean(), nullable=False, primary_key=False),
        sa.Column('created_at', sa.DateTime(), nullable=False, primary_key=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column('updated_at', sa.DateTime(), nullable=False, primary_key=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.CheckConstraint('points >= 0 AND wallet_cents >= 0 AND lifetime_cents >= 0', name=op.f('ck_commerce_members_member_balances_nonnegative')),
        sa.UniqueConstraint('store_id', 'phone', name='uq_commerce_members_store_id'),
    )
    op.create_index('ix_commerce_members_store_id', 'commerce_members', ['store_id'], unique=False)
    op.create_table('commerce_rewards',
        sa.Column('id', sa.BigInteger().with_variant(sa.Integer(), "sqlite"), nullable=False, primary_key=True),
        sa.Column('store_id', sa.BigInteger().with_variant(sa.Integer(), "sqlite"), sa.ForeignKey('stores.id'), nullable=False, primary_key=False),
        sa.Column('title', sa.String(100), nullable=False, primary_key=False),
        sa.Column('description', sa.String(500), nullable=False, primary_key=False),
        sa.Column('points_cost', sa.Integer(), nullable=False, primary_key=False),
        sa.Column('stock', sa.Integer(), nullable=False, primary_key=False),
        sa.Column('enabled', sa.Boolean(), nullable=False, primary_key=False),
        sa.Column('created_at', sa.DateTime(), nullable=False, primary_key=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column('updated_at', sa.DateTime(), nullable=False, primary_key=False, server_default=sa.text("CURRENT_TIMESTAMP")),
    )
    op.create_index('ix_commerce_rewards_store_id', 'commerce_rewards', ['store_id'], unique=False)
    op.create_table('commerce_riders',
        sa.Column('id', sa.BigInteger().with_variant(sa.Integer(), "sqlite"), nullable=False, primary_key=True),
        sa.Column('store_id', sa.BigInteger().with_variant(sa.Integer(), "sqlite"), sa.ForeignKey('stores.id'), nullable=False, primary_key=False),
        sa.Column('name', sa.String(60), nullable=False, primary_key=False),
        sa.Column('phone', sa.String(20), nullable=False, primary_key=False),
        sa.Column('enabled', sa.Boolean(), nullable=False, primary_key=False),
        sa.Column('created_at', sa.DateTime(), nullable=False, primary_key=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column('updated_at', sa.DateTime(), nullable=False, primary_key=False, server_default=sa.text("CURRENT_TIMESTAMP")),
    )
    op.create_index('ix_commerce_riders_store_id', 'commerce_riders', ['store_id'], unique=False)
    op.create_table('commerce_store_policies',
        sa.Column('store_id', sa.BigInteger().with_variant(sa.Integer(), "sqlite"), sa.ForeignKey('stores.id'), nullable=False, primary_key=True),
        sa.Column('data', sa.JSON(), nullable=False, primary_key=False),
        sa.Column('created_at', sa.DateTime(), nullable=False, primary_key=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column('updated_at', sa.DateTime(), nullable=False, primary_key=False, server_default=sa.text("CURRENT_TIMESTAMP")),
    )
    op.create_table('commerce_tasks',
        sa.Column('id', sa.BigInteger().with_variant(sa.Integer(), "sqlite"), nullable=False, primary_key=True),
        sa.Column('store_id', sa.BigInteger().with_variant(sa.Integer(), "sqlite"), sa.ForeignKey('stores.id'), nullable=False, primary_key=False),
        sa.Column('title', sa.String(100), nullable=False, primary_key=False),
        sa.Column('kind', sa.String(20), nullable=False, primary_key=False),
        sa.Column('target', sa.Integer(), nullable=False, primary_key=False),
        sa.Column('points_reward', sa.Integer(), nullable=False, primary_key=False),
        sa.Column('enabled', sa.Boolean(), nullable=False, primary_key=False),
        sa.Column('created_at', sa.DateTime(), nullable=False, primary_key=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column('updated_at', sa.DateTime(), nullable=False, primary_key=False, server_default=sa.text("CURRENT_TIMESTAMP")),
    )
    op.create_index('ix_commerce_tasks_store_id', 'commerce_tasks', ['store_id'], unique=False)
    op.create_table('commerce_addresses',
        sa.Column('id', sa.BigInteger().with_variant(sa.Integer(), "sqlite"), nullable=False, primary_key=True),
        sa.Column('store_id', sa.BigInteger().with_variant(sa.Integer(), "sqlite"), sa.ForeignKey('stores.id'), nullable=False, primary_key=False),
        sa.Column('member_id', sa.BigInteger().with_variant(sa.Integer(), "sqlite"), sa.ForeignKey('commerce_members.id'), nullable=False, primary_key=False),
        sa.Column('data', sa.JSON(), nullable=False, primary_key=False),
        sa.Column('is_default', sa.Boolean(), nullable=False, primary_key=False),
        sa.Column('last_used_at', sa.DateTime(), nullable=True, primary_key=False),
        sa.Column('created_at', sa.DateTime(), nullable=False, primary_key=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column('updated_at', sa.DateTime(), nullable=False, primary_key=False, server_default=sa.text("CURRENT_TIMESTAMP")),
    )
    op.create_index('ix_commerce_addresses_member_id', 'commerce_addresses', ['member_id'], unique=False)
    op.create_index('ix_commerce_addresses_store_id', 'commerce_addresses', ['store_id'], unique=False)
    op.create_table('commerce_coupon_claims',
        sa.Column('id', sa.BigInteger().with_variant(sa.Integer(), "sqlite"), nullable=False, primary_key=True),
        sa.Column('store_id', sa.BigInteger().with_variant(sa.Integer(), "sqlite"), sa.ForeignKey('stores.id'), nullable=False, primary_key=False),
        sa.Column('member_id', sa.BigInteger().with_variant(sa.Integer(), "sqlite"), sa.ForeignKey('commerce_members.id'), nullable=False, primary_key=False),
        sa.Column('coupon_id', sa.BigInteger().with_variant(sa.Integer(), "sqlite"), sa.ForeignKey('commerce_coupons.id'), nullable=False, primary_key=False),
        sa.Column('status', sa.String(16), nullable=False, primary_key=False),
        sa.Column('snapshot', sa.JSON(), nullable=False, primary_key=False),
        sa.Column('created_at', sa.DateTime(), nullable=False, primary_key=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column('updated_at', sa.DateTime(), nullable=False, primary_key=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.UniqueConstraint('member_id', 'coupon_id', name='uq_commerce_coupon_claims_member_id'),
    )
    op.create_index('ix_commerce_coupon_claims_member_id', 'commerce_coupon_claims', ['member_id'], unique=False)
    op.create_index('ix_commerce_coupon_claims_store_id', 'commerce_coupon_claims', ['store_id'], unique=False)
    op.create_table('commerce_ledgers',
        sa.Column('id', sa.BigInteger().with_variant(sa.Integer(), "sqlite"), nullable=False, primary_key=True),
        sa.Column('store_id', sa.BigInteger().with_variant(sa.Integer(), "sqlite"), sa.ForeignKey('stores.id'), nullable=False, primary_key=False),
        sa.Column('member_id', sa.BigInteger().with_variant(sa.Integer(), "sqlite"), sa.ForeignKey('commerce_members.id'), nullable=False, primary_key=False),
        sa.Column('kind', sa.String(12), nullable=False, primary_key=False),
        sa.Column('delta', sa.Integer(), nullable=False, primary_key=False),
        sa.Column('balance', sa.Integer(), nullable=False, primary_key=False),
        sa.Column('reason', sa.String(200), nullable=False, primary_key=False),
        sa.Column('source_key', sa.String(100), nullable=False, primary_key=False),
        sa.Column('created_at', sa.DateTime(), nullable=False, primary_key=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column('updated_at', sa.DateTime(), nullable=False, primary_key=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.UniqueConstraint('store_id', 'member_id', 'kind', 'source_key', name='uq_commerce_ledgers_store_id'),
    )
    op.create_index('ix_commerce_ledgers_member_id', 'commerce_ledgers', ['member_id'], unique=False)
    op.create_index('ix_commerce_ledgers_store_id', 'commerce_ledgers', ['store_id'], unique=False)
    op.create_table('commerce_orders',
        sa.Column('id', sa.BigInteger().with_variant(sa.Integer(), "sqlite"), nullable=False, primary_key=True),
        sa.Column('number', sa.String(40), nullable=False, primary_key=False),
        sa.Column('store_id', sa.BigInteger().with_variant(sa.Integer(), "sqlite"), sa.ForeignKey('stores.id'), nullable=False, primary_key=False),
        sa.Column('member_id', sa.BigInteger().with_variant(sa.Integer(), "sqlite"), sa.ForeignKey('commerce_members.id'), nullable=False, primary_key=False),
        sa.Column('request_key', sa.String(64), nullable=False, primary_key=False),
        sa.Column('request_hash', sa.String(64), nullable=False, primary_key=False),
        sa.Column('status', sa.String(24), nullable=False, primary_key=False),
        sa.Column('fulfillment', sa.String(16), nullable=False, primary_key=False),
        sa.Column('contact', sa.String(60), nullable=False, primary_key=False),
        sa.Column('phone', sa.String(20), nullable=False, primary_key=False),
        sa.Column('note', sa.String(500), nullable=False, primary_key=False),
        sa.Column('table_number', sa.String(30), nullable=False, primary_key=False),
        sa.Column('items', sa.JSON(), nullable=False, primary_key=False),
        sa.Column('address', sa.JSON(), nullable=True, primary_key=False),
        sa.Column('delivery_snapshot', sa.JSON(), nullable=True, primary_key=False),
        sa.Column('subtotal_cents', sa.Integer(), nullable=False, primary_key=False),
        sa.Column('packaging_cents', sa.Integer(), nullable=False, primary_key=False),
        sa.Column('delivery_cents', sa.Integer(), nullable=False, primary_key=False),
        sa.Column('discount_cents', sa.Integer(), nullable=False, primary_key=False),
        sa.Column('total_cents', sa.Integer(), nullable=False, primary_key=False),
        sa.Column('coupon_claim_id', sa.BigInteger().with_variant(sa.Integer(), "sqlite"), nullable=True, primary_key=False),
        sa.Column('rider_id', sa.BigInteger().with_variant(sa.Integer(), "sqlite"), sa.ForeignKey('commerce_riders.id'), nullable=True, primary_key=False),
        sa.Column('events', sa.JSON(), nullable=False, primary_key=False),
        sa.Column('created_at', sa.DateTime(), nullable=False, primary_key=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column('updated_at', sa.DateTime(), nullable=False, primary_key=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.CheckConstraint('total_cents >= 0 AND subtotal_cents >= 0 AND discount_cents >= 0', name=op.f('ck_commerce_orders_order_amounts_nonnegative')),
        sa.UniqueConstraint('store_id', 'member_id', 'request_key', name='uq_commerce_orders_store_id'),
    )
    op.create_index('ix_commerce_orders_member_id', 'commerce_orders', ['member_id'], unique=False)
    op.create_index('ix_commerce_orders_number', 'commerce_orders', ['number'], unique=True)
    op.create_index('ix_commerce_orders_status', 'commerce_orders', ['status'], unique=False)
    op.create_index('ix_commerce_orders_store_id', 'commerce_orders', ['store_id'], unique=False)
    op.create_table('commerce_redemptions',
        sa.Column('id', sa.BigInteger().with_variant(sa.Integer(), "sqlite"), nullable=False, primary_key=True),
        sa.Column('store_id', sa.BigInteger().with_variant(sa.Integer(), "sqlite"), sa.ForeignKey('stores.id'), nullable=False, primary_key=False),
        sa.Column('member_id', sa.BigInteger().with_variant(sa.Integer(), "sqlite"), sa.ForeignKey('commerce_members.id'), nullable=False, primary_key=False),
        sa.Column('reward_id', sa.BigInteger().with_variant(sa.Integer(), "sqlite"), sa.ForeignKey('commerce_rewards.id'), nullable=False, primary_key=False),
        sa.Column('request_key', sa.String(64), nullable=False, primary_key=False),
        sa.Column('code', sa.String(30), nullable=False, primary_key=False),
        sa.Column('title', sa.String(100), nullable=False, primary_key=False),
        sa.Column('points_cost', sa.Integer(), nullable=False, primary_key=False),
        sa.Column('status', sa.String(20), nullable=False, primary_key=False),
        sa.Column('created_at', sa.DateTime(), nullable=False, primary_key=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column('updated_at', sa.DateTime(), nullable=False, primary_key=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.UniqueConstraint('code', name='uq_commerce_redemptions_code'),
        sa.UniqueConstraint('member_id', 'request_key', name='uq_commerce_redemptions_member_id'),
    )
    op.create_index('ix_commerce_redemptions_member_id', 'commerce_redemptions', ['member_id'], unique=False)
    op.create_index('ix_commerce_redemptions_store_id', 'commerce_redemptions', ['store_id'], unique=False)
    op.create_table('commerce_sessions',
        sa.Column('id', sa.BigInteger().with_variant(sa.Integer(), "sqlite"), nullable=False, primary_key=True),
        sa.Column('store_id', sa.BigInteger().with_variant(sa.Integer(), "sqlite"), sa.ForeignKey('stores.id'), nullable=False, primary_key=False),
        sa.Column('member_id', sa.BigInteger().with_variant(sa.Integer(), "sqlite"), sa.ForeignKey('commerce_members.id'), nullable=False, primary_key=False),
        sa.Column('token_hash', sa.String(64), nullable=False, primary_key=False),
        sa.Column('device_name', sa.String(80), nullable=False, primary_key=False),
        sa.Column('expires_at', sa.DateTime(), nullable=False, primary_key=False),
        sa.Column('revoked', sa.Boolean(), nullable=False, primary_key=False),
        sa.Column('created_at', sa.DateTime(), nullable=False, primary_key=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column('updated_at', sa.DateTime(), nullable=False, primary_key=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.UniqueConstraint('token_hash', name='uq_commerce_sessions_token_hash'),
    )
    op.create_index('ix_commerce_sessions_member_id', 'commerce_sessions', ['member_id'], unique=False)
    op.create_index('ix_commerce_sessions_store_id', 'commerce_sessions', ['store_id'], unique=False)
    op.create_table('commerce_dish_options',
        sa.Column('dish_id', sa.BigInteger().with_variant(sa.Integer(), "sqlite"), sa.ForeignKey('dishes.id'), nullable=False, primary_key=True),
        sa.Column('store_id', sa.BigInteger().with_variant(sa.Integer(), "sqlite"), sa.ForeignKey('stores.id'), nullable=False, primary_key=False),
        sa.Column('groups', sa.JSON(), nullable=False, primary_key=False),
        sa.Column('created_at', sa.DateTime(), nullable=False, primary_key=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column('updated_at', sa.DateTime(), nullable=False, primary_key=False, server_default=sa.text("CURRENT_TIMESTAMP")),
    )
    op.create_index('ix_commerce_dish_options_store_id', 'commerce_dish_options', ['store_id'], unique=False)

def downgrade():
    op.drop_table('commerce_dish_options')
    op.drop_table('commerce_sessions')
    op.drop_table('commerce_redemptions')
    op.drop_table('commerce_orders')
    op.drop_table('commerce_ledgers')
    op.drop_table('commerce_coupon_claims')
    op.drop_table('commerce_addresses')
    op.drop_table('commerce_tasks')
    op.drop_table('commerce_store_policies')
    op.drop_table('commerce_riders')
    op.drop_table('commerce_rewards')
    op.drop_table('commerce_members')
    op.drop_table('commerce_coupons')
    op.drop_table('commerce_audit_events')
