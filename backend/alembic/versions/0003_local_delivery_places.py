"""Configure local common delivery places without a map provider.

Revision ID: 0003_local_delivery_places
Revises: 0002_delivery_settings
"""

from alembic import op
import sqlalchemy as sa

revision = "0003_local_delivery_places"
down_revision = "0002_delivery_settings"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("stores", sa.Column("delivery_places", sa.JSON(), nullable=False, server_default=sa.text("'[]'")))


def downgrade() -> None:
    op.drop_column("stores", "delivery_places")
