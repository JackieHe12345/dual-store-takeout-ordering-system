from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, Boolean, ForeignKey, Integer, String, Table, Column, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.store import Store

ID_TYPE = BigInteger().with_variant(Integer, "sqlite")

role_permissions = Table(
    "role_permissions",
    Base.metadata,
    Column("role_id", ID_TYPE, ForeignKey("roles.id", ondelete="CASCADE"), primary_key=True),
    Column(
        "permission_id",
        ID_TYPE,
        ForeignKey("permissions.id", ondelete="CASCADE"),
        primary_key=True,
    ),
)


class Role(Base):
    __tablename__ = "roles"
    __table_args__ = (UniqueConstraint("code"),)

    id: Mapped[int] = mapped_column(ID_TYPE, primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(String(40), index=True)
    name: Mapped[str] = mapped_column(String(80))
    permissions: Mapped[list[Permission]] = relationship(
        secondary=role_permissions, back_populates="roles", lazy="selectin"
    )


class Permission(Base):
    __tablename__ = "permissions"
    __table_args__ = (UniqueConstraint("code"),)

    id: Mapped[int] = mapped_column(ID_TYPE, primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(String(80), index=True)
    description: Mapped[str] = mapped_column(String(200))
    roles: Mapped[list[Role]] = relationship(
        secondary=role_permissions, back_populates="permissions", lazy="selectin"
    )


class AdminUser(TimestampMixin, Base):
    __tablename__ = "admin_users"
    __table_args__ = (UniqueConstraint("username"),)

    id: Mapped[int] = mapped_column(ID_TYPE, primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(String(80), index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    display_name: Mapped[str] = mapped_column(String(120))
    role_id: Mapped[int] = mapped_column(ID_TYPE, ForeignKey("roles.id", ondelete="RESTRICT"))
    store_id: Mapped[int | None] = mapped_column(
        ID_TYPE, ForeignKey("stores.id", ondelete="RESTRICT"), index=True
    )
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    last_login_at: Mapped[datetime | None]

    role: Mapped[Role] = relationship(lazy="selectin")
    store: Mapped[Store | None] = relationship(back_populates="admin_users")
