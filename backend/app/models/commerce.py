"""Store-scoped commerce records for ordering and membership without payment processing."""
from __future__ import annotations

from datetime import datetime
from sqlalchemy import BigInteger, Boolean, CheckConstraint, ForeignKey, Integer, JSON, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from app.models.base import Base, TimestampMixin as BaseTimestampMixin

ID = BigInteger().with_variant(Integer, "sqlite")

class TimestampMixin(BaseTimestampMixin):
    __mapper_args__ = {"eager_defaults": True}

class Member(TimestampMixin, Base):
    __tablename__ = "commerce_members"
    __table_args__ = (UniqueConstraint("store_id", "phone"), CheckConstraint("points >= 0 AND wallet_cents >= 0 AND lifetime_cents >= 0", name="member_balances_nonnegative"))
    id: Mapped[int] = mapped_column(ID, primary_key=True)
    store_id: Mapped[int] = mapped_column(ID, ForeignKey("stores.id"), index=True)
    phone: Mapped[str] = mapped_column(String(20))
    password_hash: Mapped[str] = mapped_column(String(500))
    name: Mapped[str] = mapped_column(String(60), default="")
    birthday: Mapped[str | None] = mapped_column(String(10))
    points: Mapped[int] = mapped_column(Integer, default=0)
    wallet_cents: Mapped[int] = mapped_column(Integer, default=0)
    lifetime_cents: Mapped[int] = mapped_column(BigInteger, default=0)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)

class MemberSession(TimestampMixin, Base):
    __tablename__ = "commerce_sessions"
    id: Mapped[int] = mapped_column(ID, primary_key=True)
    store_id: Mapped[int] = mapped_column(ID, ForeignKey("stores.id"), index=True)
    member_id: Mapped[int] = mapped_column(ID, ForeignKey("commerce_members.id"), index=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    device_name: Mapped[str] = mapped_column(String(80))
    expires_at: Mapped[datetime]
    revoked: Mapped[bool] = mapped_column(Boolean, default=False)

class MemberAddress(TimestampMixin, Base):
    __tablename__ = "commerce_addresses"
    id: Mapped[int] = mapped_column(ID, primary_key=True)
    store_id: Mapped[int] = mapped_column(ID, ForeignKey("stores.id"), index=True)
    member_id: Mapped[int] = mapped_column(ID, ForeignKey("commerce_members.id"), index=True)
    data: Mapped[dict] = mapped_column(JSON)
    is_default: Mapped[bool] = mapped_column(Boolean, default=False)
    last_used_at: Mapped[datetime | None]

class StorePolicy(TimestampMixin, Base):
    __tablename__ = "commerce_store_policies"
    store_id: Mapped[int] = mapped_column(ID, ForeignKey("stores.id"), primary_key=True)
    data: Mapped[dict] = mapped_column(JSON)

class DishOptions(TimestampMixin, Base):
    __tablename__ = "commerce_dish_options"
    dish_id: Mapped[int] = mapped_column(ID, ForeignKey("dishes.id"), primary_key=True)
    store_id: Mapped[int] = mapped_column(ID, ForeignKey("stores.id"), index=True)
    groups: Mapped[list] = mapped_column(JSON, default=list)

class Rider(TimestampMixin, Base):
    __tablename__ = "commerce_riders"
    id: Mapped[int] = mapped_column(ID, primary_key=True)
    store_id: Mapped[int] = mapped_column(ID, ForeignKey("stores.id"), index=True)
    name: Mapped[str] = mapped_column(String(60))
    phone: Mapped[str] = mapped_column(String(20))
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)

class Order(TimestampMixin, Base):
    __tablename__ = "commerce_orders"
    __table_args__ = (UniqueConstraint("store_id", "member_id", "request_key"), CheckConstraint("total_cents >= 0 AND subtotal_cents >= 0 AND discount_cents >= 0", name="order_amounts_nonnegative"))
    id: Mapped[int] = mapped_column(ID, primary_key=True)
    number: Mapped[str] = mapped_column(String(40), unique=True, index=True)
    store_id: Mapped[int] = mapped_column(ID, ForeignKey("stores.id"), index=True)
    member_id: Mapped[int] = mapped_column(ID, ForeignKey("commerce_members.id"), index=True)
    request_key: Mapped[str] = mapped_column(String(64))
    request_hash: Mapped[str] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(24), default="PENDING", index=True)
    fulfillment: Mapped[str] = mapped_column(String(16))
    contact: Mapped[str] = mapped_column(String(60))
    phone: Mapped[str] = mapped_column(String(20))
    note: Mapped[str] = mapped_column(String(500), default="")
    table_number: Mapped[str] = mapped_column(String(30), default="")
    items: Mapped[list] = mapped_column(JSON)
    address: Mapped[dict | None] = mapped_column(JSON)
    delivery_snapshot: Mapped[dict | None] = mapped_column(JSON)
    subtotal_cents: Mapped[int] = mapped_column(Integer)
    packaging_cents: Mapped[int] = mapped_column(Integer)
    delivery_cents: Mapped[int] = mapped_column(Integer)
    discount_cents: Mapped[int] = mapped_column(Integer)
    total_cents: Mapped[int] = mapped_column(Integer)
    coupon_claim_id: Mapped[int | None] = mapped_column(ID)
    rider_id: Mapped[int | None] = mapped_column(ID, ForeignKey("commerce_riders.id"))
    events: Mapped[list] = mapped_column(JSON, default=list)

class Ledger(TimestampMixin, Base):
    __tablename__ = "commerce_ledgers"
    __table_args__ = (UniqueConstraint("store_id", "member_id", "kind", "source_key"),)
    id: Mapped[int] = mapped_column(ID, primary_key=True)
    store_id: Mapped[int] = mapped_column(ID, ForeignKey("stores.id"), index=True)
    member_id: Mapped[int] = mapped_column(ID, ForeignKey("commerce_members.id"), index=True)
    kind: Mapped[str] = mapped_column(String(12))
    delta: Mapped[int] = mapped_column(Integer)
    balance: Mapped[int] = mapped_column(Integer)
    reason: Mapped[str] = mapped_column(String(200))
    source_key: Mapped[str] = mapped_column(String(100))

class Coupon(TimestampMixin, Base):
    __tablename__ = "commerce_coupons"
    id: Mapped[int] = mapped_column(ID, primary_key=True)
    store_id: Mapped[int] = mapped_column(ID, ForeignKey("stores.id"), index=True)
    title: Mapped[str] = mapped_column(String(100))
    amount_cents: Mapped[int] = mapped_column(Integer)
    minimum_cents: Mapped[int] = mapped_column(Integer, default=0)
    quantity: Mapped[int] = mapped_column(Integer)
    starts_at: Mapped[datetime]
    expires_at: Mapped[datetime]
    birthday_only: Mapped[bool] = mapped_column(Boolean, default=False)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)

class CouponClaim(TimestampMixin, Base):
    __tablename__ = "commerce_coupon_claims"
    __table_args__ = (UniqueConstraint("member_id", "coupon_id"),)
    id: Mapped[int] = mapped_column(ID, primary_key=True)
    store_id: Mapped[int] = mapped_column(ID, ForeignKey("stores.id"), index=True)
    member_id: Mapped[int] = mapped_column(ID, ForeignKey("commerce_members.id"), index=True)
    coupon_id: Mapped[int] = mapped_column(ID, ForeignKey("commerce_coupons.id"))
    status: Mapped[str] = mapped_column(String(16), default="AVAILABLE")
    snapshot: Mapped[dict] = mapped_column(JSON)

class Reward(TimestampMixin, Base):
    __tablename__ = "commerce_rewards"
    id: Mapped[int] = mapped_column(ID, primary_key=True)
    store_id: Mapped[int] = mapped_column(ID, ForeignKey("stores.id"), index=True)
    title: Mapped[str] = mapped_column(String(100))
    description: Mapped[str] = mapped_column(String(500), default="")
    points_cost: Mapped[int] = mapped_column(Integer)
    stock: Mapped[int] = mapped_column(Integer)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)

class Redemption(TimestampMixin, Base):
    __tablename__ = "commerce_redemptions"
    __table_args__ = (UniqueConstraint("member_id", "request_key"),)
    id: Mapped[int] = mapped_column(ID, primary_key=True)
    store_id: Mapped[int] = mapped_column(ID, ForeignKey("stores.id"), index=True)
    member_id: Mapped[int] = mapped_column(ID, ForeignKey("commerce_members.id"), index=True)
    reward_id: Mapped[int] = mapped_column(ID, ForeignKey("commerce_rewards.id"))
    request_key: Mapped[str] = mapped_column(String(64))
    code: Mapped[str] = mapped_column(String(30), unique=True)
    title: Mapped[str] = mapped_column(String(100))
    points_cost: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(20), default="PENDING")

class GrowthTask(TimestampMixin, Base):
    __tablename__ = "commerce_tasks"
    id: Mapped[int] = mapped_column(ID, primary_key=True)
    store_id: Mapped[int] = mapped_column(ID, ForeignKey("stores.id"), index=True)
    title: Mapped[str] = mapped_column(String(100))
    kind: Mapped[str] = mapped_column(String(20))
    target: Mapped[int] = mapped_column(Integer)
    points_reward: Mapped[int] = mapped_column(Integer)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)

class AuditEvent(TimestampMixin, Base):
    __tablename__ = "commerce_audit_events"
    id: Mapped[int] = mapped_column(ID, primary_key=True)
    store_id: Mapped[int] = mapped_column(ID, ForeignKey("stores.id"), index=True)
    actor: Mapped[str] = mapped_column(String(80))
    action: Mapped[str] = mapped_column(String(80))
    subject: Mapped[str] = mapped_column(String(100))
    detail: Mapped[dict] = mapped_column(JSON, default=dict)
