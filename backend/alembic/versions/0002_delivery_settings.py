"""Confirm store locations and configure distance-based delivery fees.

Revision ID: 0002_delivery_settings
Revises: 0001_stage1
"""

from alembic import op
import sqlalchemy as sa

revision = "0002_delivery_settings"
down_revision = "0001_stage1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("stores", sa.Column("delivery_city", sa.String(80), nullable=True))
    op.add_column("stores", sa.Column("delivery_location_confirmed", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column("stores", sa.Column("delivery_fee_tiers", sa.JSON(), nullable=False, server_default=sa.text("'[]'")))


def downgrade() -> None:
    op.drop_column("stores", "delivery_fee_tiers")
    op.drop_column("stores", "delivery_location_confirmed")
    op.drop_column("stores", "delivery_city")
