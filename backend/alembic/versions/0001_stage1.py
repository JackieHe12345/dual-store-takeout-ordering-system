"""Stage 1: stores, domains, roles, users and menu catalog.

Revision ID: 0001_stage1
Revises: None
Create Date: 2026-09-15
"""

from typing import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "0001_stage1"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

coordinate_system = sa.Enum(
    "GCJ_02", "BD_09", "WGS_84", name="coordinatesystem", native_enum=False, length=16
)
domain_type = sa.Enum("CUSTOMER", "STAFF", name="domaintype", native_enum=False, length=16)


def upgrade() -> None:
    op.create_table(
        "stores",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("slug", sa.String(80), nullable=False),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("logo_url", sa.String(500), nullable=True),
        sa.Column("phone", sa.String(32), nullable=False),
        sa.Column("address", sa.String(500), nullable=False),
        sa.Column("latitude", sa.Numeric(10, 7), nullable=False),
        sa.Column("longitude", sa.Numeric(10, 7), nullable=False),
        sa.Column("coordinate_system", coordinate_system, nullable=False),
        sa.Column("delivery_radius_meters", sa.Integer(), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("delivery_radius_meters > 0", name="ck_stores_delivery_radius_positive"),
        sa.PrimaryKeyConstraint("id", name="pk_stores"),
        sa.UniqueConstraint("slug", name="uq_stores_slug"),
    )
    op.create_index("ix_stores_enabled", "stores", ["enabled"])
    op.create_index("ix_stores_slug", "stores", ["slug"])

    op.create_table(
        "permissions",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("code", sa.String(80), nullable=False),
        sa.Column("description", sa.String(200), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_permissions"),
        sa.UniqueConstraint("code", name="uq_permissions_code"),
    )
    op.create_index("ix_permissions_code", "permissions", ["code"])

    op.create_table(
        "roles",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("code", sa.String(40), nullable=False),
        sa.Column("name", sa.String(80), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_roles"),
        sa.UniqueConstraint("code", name="uq_roles_code"),
    )
    op.create_index("ix_roles_code", "roles", ["code"])

    op.create_table(
        "store_domains",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("store_id", sa.BigInteger(), nullable=False),
        sa.Column("domain", sa.String(253), nullable=False),
        sa.Column("domain_type", domain_type, nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(
            ["store_id"], ["stores.id"], name="fk_store_domains_store_id_stores", ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name="pk_store_domains"),
        sa.UniqueConstraint("domain", name="uq_store_domains_domain"),
    )
    op.create_index("ix_store_domains_domain", "store_domains", ["domain"])
    op.create_index("ix_store_domains_domain_type", "store_domains", ["domain_type"])
    op.create_index("ix_store_domains_enabled", "store_domains", ["enabled"])
    op.create_index("ix_store_domains_store_id", "store_domains", ["store_id"])

    op.create_table(
        "role_permissions",
        sa.Column("role_id", sa.BigInteger(), nullable=False),
        sa.Column("permission_id", sa.BigInteger(), nullable=False),
        sa.ForeignKeyConstraint(
            ["permission_id"],
            ["permissions.id"],
            name="fk_role_permissions_permission_id_permissions",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["role_id"], ["roles.id"], name="fk_role_permissions_role_id_roles", ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("role_id", "permission_id", name="pk_role_permissions"),
    )

    op.create_table(
        "admin_users",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("username", sa.String(80), nullable=False),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("display_name", sa.String(120), nullable=False),
        sa.Column("role_id", sa.BigInteger(), nullable=False),
        sa.Column("store_id", sa.BigInteger(), nullable=True),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("last_login_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(
            ["role_id"], ["roles.id"], name="fk_admin_users_role_id_roles", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["store_id"], ["stores.id"], name="fk_admin_users_store_id_stores", ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id", name="pk_admin_users"),
        sa.UniqueConstraint("username", name="uq_admin_users_username"),
    )
    op.create_index("ix_admin_users_enabled", "admin_users", ["enabled"])
    op.create_index("ix_admin_users_store_id", "admin_users", ["store_id"])
    op.create_index("ix_admin_users_username", "admin_users", ["username"])

    op.create_table(
        "categories",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("store_id", sa.BigInteger(), nullable=False),
        sa.Column("name", sa.String(80), nullable=False),
        sa.Column("slug", sa.String(80), nullable=False),
        sa.Column("description", sa.String(300), nullable=True),
        sa.Column("icon", sa.String(80), nullable=True),
        sa.Column("sort_order", sa.Integer(), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(
            ["store_id"], ["stores.id"], name="fk_categories_store_id_stores", ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name="pk_categories"),
        sa.UniqueConstraint("id", "store_id", name="uq_categories_id_store_id"),
        sa.UniqueConstraint("store_id", "slug", name="uq_categories_store_id_slug"),
    )
    op.create_index("ix_categories_enabled", "categories", ["enabled"])
    op.create_index("ix_categories_store_id", "categories", ["store_id"])

    op.create_table(
        "dishes",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("store_id", sa.BigInteger(), nullable=False),
        sa.Column("category_id", sa.BigInteger(), nullable=False),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("slug", sa.String(100), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("image_url", sa.String(500), nullable=True),
        sa.Column("price_cents", sa.Integer(), nullable=False),
        sa.Column("original_price_cents", sa.Integer(), nullable=True),
        sa.Column("monthly_sales", sa.Integer(), nullable=False),
        sa.Column("stock", sa.Integer(), nullable=True),
        sa.Column("requires_options", sa.Boolean(), nullable=False),
        sa.Column("sold_out", sa.Boolean(), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("monthly_sales >= 0", name="ck_dishes_monthly_sales_nonnegative"),
        sa.CheckConstraint(
            "original_price_cents IS NULL OR original_price_cents >= price_cents",
            name="ck_dishes_original_price_valid",
        ),
        sa.CheckConstraint("price_cents >= 0", name="ck_dishes_price_nonnegative"),
        sa.CheckConstraint("stock IS NULL OR stock >= 0", name="ck_dishes_stock_nonnegative"),
        sa.ForeignKeyConstraint(
            ["category_id", "store_id"],
            ["categories.id", "categories.store_id"],
            name="fk_dishes_category_store",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["store_id"], ["stores.id"], name="fk_dishes_store_id_stores", ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name="pk_dishes"),
        sa.UniqueConstraint("store_id", "slug", name="uq_dishes_store_id_slug"),
    )
    op.create_index("ix_dishes_category_id", "dishes", ["category_id"])
    op.create_index("ix_dishes_enabled", "dishes", ["enabled"])
    op.create_index("ix_dishes_sold_out", "dishes", ["sold_out"])
    op.create_index("ix_dishes_store_id", "dishes", ["store_id"])


def downgrade() -> None:
    op.drop_table("dishes")
    op.drop_table("categories")
    op.drop_table("admin_users")
    op.drop_table("role_permissions")
    op.drop_table("store_domains")
    op.drop_table("roles")
    op.drop_table("permissions")
    op.drop_table("stores")
