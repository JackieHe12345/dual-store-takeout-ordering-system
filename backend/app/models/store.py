from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, Boolean, CheckConstraint, Enum, ForeignKey, Integer, JSON, Numeric, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin
from app.models.enums import CoordinateSystem, DomainType

if TYPE_CHECKING:
    from app.models.admin_user import AdminUser
    from app.models.catalog import Category, Dish

ID_TYPE = BigInteger().with_variant(Integer, "sqlite")


class Store(TimestampMixin, Base):
    __tablename__ = "stores"
    __table_args__ = (
        UniqueConstraint("slug"),
        CheckConstraint("delivery_radius_meters > 0", name="delivery_radius_positive"),
    )

    id: Mapped[int] = mapped_column(ID_TYPE, primary_key=True, autoincrement=True)
    slug: Mapped[str] = mapped_column(String(80), index=True)
    name: Mapped[str] = mapped_column(String(120))
    logo_url: Mapped[str | None] = mapped_column(String(500))
    phone: Mapped[str] = mapped_column(String(32))
    address: Mapped[str] = mapped_column(String(500))
    latitude: Mapped[Decimal] = mapped_column(Numeric(10, 7))
    longitude: Mapped[Decimal] = mapped_column(Numeric(10, 7))
    coordinate_system: Mapped[CoordinateSystem] = mapped_column(
        Enum(CoordinateSystem, native_enum=False, length=16), default=CoordinateSystem.GCJ_02
    )
    delivery_radius_meters: Mapped[int] = mapped_column(Integer, default=5000)
    delivery_city: Mapped[str | None] = mapped_column(String(80))
    # Seed and existing coordinates are examples until a manager confirms them.
    delivery_location_confirmed: Mapped[bool] = mapped_column(Boolean, default=False)
    delivery_fee_tiers: Mapped[list[dict[str, int]]] = mapped_column(JSON, default=list)
    delivery_places: Mapped[list[dict]] = mapped_column(JSON, default=list)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, index=True)

    domains: Mapped[list[StoreDomain]] = relationship(
        back_populates="store", cascade="all, delete-orphan"
    )
    categories: Mapped[list[Category]] = relationship(back_populates="store")
    dishes: Mapped[list[Dish]] = relationship(back_populates="store", overlaps="dishes")
    admin_users: Mapped[list[AdminUser]] = relationship(back_populates="store")


class StoreDomain(Base):
    __tablename__ = "store_domains"
    __table_args__ = (UniqueConstraint("domain", name="uq_store_domains_domain"),)

    id: Mapped[int] = mapped_column(ID_TYPE, primary_key=True, autoincrement=True)
    store_id: Mapped[int] = mapped_column(
        ID_TYPE, ForeignKey("stores.id", ondelete="CASCADE"), index=True
    )
    domain: Mapped[str] = mapped_column(String(253), index=True)
    domain_type: Mapped[DomainType] = mapped_column(
        Enum(DomainType, native_enum=False, length=16), index=True
    )
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now(), nullable=False)

    store: Mapped[Store] = relationship(back_populates="domains")
