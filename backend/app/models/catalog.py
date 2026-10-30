from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, Boolean, CheckConstraint, ForeignKey, ForeignKeyConstraint, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.store import Store

ID_TYPE = BigInteger().with_variant(Integer, "sqlite")


class Category(TimestampMixin, Base):
    __tablename__ = "categories"
    __table_args__ = (
        UniqueConstraint("id", "store_id", name="uq_categories_id_store_id"),
        UniqueConstraint("store_id", "slug", name="uq_categories_store_id_slug"),
    )

    id: Mapped[int] = mapped_column(ID_TYPE, primary_key=True, autoincrement=True)
    store_id: Mapped[int] = mapped_column(
        ID_TYPE, ForeignKey("stores.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(80))
    slug: Mapped[str] = mapped_column(String(80))
    description: Mapped[str | None] = mapped_column(String(300))
    icon: Mapped[str | None] = mapped_column(String(80))
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, index=True)

    store: Mapped[Store] = relationship(back_populates="categories")
    dishes: Mapped[list[Dish]] = relationship(
        back_populates="category", cascade="all, delete-orphan"
    )


class Dish(TimestampMixin, Base):
    __tablename__ = "dishes"
    __table_args__ = (
        ForeignKeyConstraint(
            ["category_id", "store_id"],
            ["categories.id", "categories.store_id"],
            ondelete="CASCADE",
            name="fk_dishes_category_store",
        ),
        UniqueConstraint("store_id", "slug", name="uq_dishes_store_id_slug"),
        CheckConstraint("price_cents >= 0", name="price_nonnegative"),
        CheckConstraint(
            "original_price_cents IS NULL OR original_price_cents >= price_cents",
            name="original_price_valid",
        ),
        CheckConstraint("monthly_sales >= 0", name="monthly_sales_nonnegative"),
        CheckConstraint("stock IS NULL OR stock >= 0", name="stock_nonnegative"),
    )

    id: Mapped[int] = mapped_column(ID_TYPE, primary_key=True, autoincrement=True)
    store_id: Mapped[int] = mapped_column(
        ID_TYPE, ForeignKey("stores.id", ondelete="CASCADE"), index=True
    )
    category_id: Mapped[int] = mapped_column(ID_TYPE, index=True)
    name: Mapped[str] = mapped_column(String(120))
    slug: Mapped[str] = mapped_column(String(100))
    description: Mapped[str | None] = mapped_column(Text)
    image_url: Mapped[str | None] = mapped_column(String(500))
    price_cents: Mapped[int] = mapped_column(Integer)
    original_price_cents: Mapped[int | None] = mapped_column(Integer)
    monthly_sales: Mapped[int] = mapped_column(Integer, default=0)
    stock: Mapped[int | None] = mapped_column(Integer)
    requires_options: Mapped[bool] = mapped_column(Boolean, default=False)
    sold_out: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)

    store: Mapped[Store] = relationship(back_populates="dishes", overlaps="category,dishes")
    category: Mapped[Category] = relationship(back_populates="dishes", overlaps="dishes,store")
