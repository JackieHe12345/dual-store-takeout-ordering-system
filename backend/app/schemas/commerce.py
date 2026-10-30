from __future__ import annotations
from datetime import date, datetime, timezone
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from app.schemas.delivery import Coordinates

class Input(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True, allow_inf_nan=False)

class MemberCredentials(Input):
    phone: str = Field(pattern=r"^1[3-9]\d{9}$")
    password: str = Field(min_length=10, max_length=100)
    device_name: str = Field(default="当前设备", min_length=1, max_length=80)

class ProfileUpdate(Input):
    name: str = Field(min_length=1, max_length=60)
    birthday: date | None = None
    @field_validator("birthday")
    @classmethod
    def past_birthday(cls, v):
        if v and (v > date.today() or v.year < 1900): raise ValueError("生日不正确")
        return v

class AddressInput(Coordinates):
    contact: str = Field(min_length=1, max_length=60)
    phone: str = Field(pattern=r"^1[3-9]\d{9}$")
    title: str = Field(min_length=1, max_length=120)
    detail: str = Field(min_length=1, max_length=500)
    is_default: bool = False

class MemberCorrection(ProfileUpdate):
    reason: str = Field(min_length=3, max_length=200)

class StoreIdentity(Input):
    name: str = Field(min_length=1, max_length=100)
    phone: str = Field(min_length=3, max_length=30, pattern=r"^[0-9+() -]+$")

class Hours(Input):
    day: int = Field(ge=0, le=6, strict=True)
    start: str = Field(pattern=r"^(?:[01]\d|2[0-3]):[0-5]\d$")
    end: str = Field(pattern=r"^(?:(?:[01]\d|2[0-3]):[0-5]\d|24:00)$")
    @model_validator(mode="after")
    def ordered(self):
        if self.start >= self.end: raise ValueError("营业时间须在同一天内，开始早于结束；跨午夜请拆成两段")
        return self

class Tier(Input):
    name: str = Field(min_length=1, max_length=30)
    threshold_cents: int = Field(ge=0, le=100000000, strict=True)

class PolicyInput(Input):
    accepting_orders: bool = True
    hours: list[Hours] = Field(default_factory=list, max_length=28)
    fulfillments: list[Literal["pickup", "dine_in", "delivery"]] = Field(default_factory=lambda: ["pickup", "dine_in", "delivery"], min_length=1, max_length=3)
    minimum_delivery_cents: int = Field(default=0, ge=0, le=1000000, strict=True)
    packaging_per_item_cents: int = Field(default=0, ge=0, le=10000, strict=True)
    points_per_yuan: int = Field(default=1, ge=0, le=100, strict=True)
    announcement: str = Field(default="", max_length=300)
    tiers: list[Tier] = Field(default_factory=lambda: [Tier(name="普通会员", threshold_cents=0), Tier(name="银卡会员", threshold_cents=100000), Tier(name="金卡会员", threshold_cents=300000)], min_length=1, max_length=10)
    @model_validator(mode="after")
    def validate_policy(self):
        thresholds=[x.threshold_cents for x in self.tiers]
        if thresholds[0] != 0 or thresholds != sorted(set(thresholds)): raise ValueError("等级须从零开始，门槛严格递增")
        for day in range(7):
            slots=sorted((h.start,h.end) for h in self.hours if h.day==day)
            if any(a[1]>b[0] for a,b in zip(slots,slots[1:])): raise ValueError("营业时段不能重叠")
        return self

class Option(Input):
    id: str = Field(pattern=r"^[a-zA-Z0-9_-]{1,40}$")
    name: str = Field(min_length=1, max_length=60)
    price_cents: int = Field(default=0, ge=0, le=100000, strict=True)
    enabled: bool = True

class OptionGroup(Input):
    id: str = Field(pattern=r"^[a-zA-Z0-9_-]{1,40}$")
    name: str = Field(min_length=1, max_length=60)
    minimum: int = Field(default=0, ge=0, le=10, strict=True)
    maximum: int = Field(default=1, ge=1, le=10, strict=True)
    options: list[Option] = Field(min_length=1, max_length=30)
    @model_validator(mode="after")
    def valid_group(self):
        ids=[o.id for o in self.options]
        if len(ids)!=len(set(ids)): raise ValueError("选项标识重复")
        if self.minimum>self.maximum or self.minimum>sum(o.enabled for o in self.options): raise ValueError("必选数量超过可用选项")
        return self

class OptionsInput(Input):
    groups: list[OptionGroup] = Field(default_factory=list, max_length=10)
    @model_validator(mode="after")
    def valid_groups(self):
        ids=[g.id for g in self.groups]
        if len(ids)!=len(set(ids)): raise ValueError("规格组标识重复")
        return self

class CartItem(Input):
    dish_id: int = Field(gt=0, strict=True)
    quantity: int = Field(ge=1, le=99, strict=True)
    options: dict[str, list[str]] = Field(default_factory=dict, max_length=10)

class OrderDraft(Input):
    items: list[CartItem] = Field(min_length=1, max_length=50)
    fulfillment: Literal["pickup", "dine_in", "delivery"]
    contact: str = Field(min_length=1, max_length=60)
    phone: str = Field(pattern=r"^1[3-9]\d{9}$")
    note: str = Field(default="", max_length=500)
    table_number: str = Field(default="", max_length=30)
    address: AddressInput | None = None
    coupon_claim_id: int | None = Field(default=None, gt=0, strict=True)
    @model_validator(mode="after")
    def required_address(self):
        if self.fulfillment == "delivery" and self.address is None: raise ValueError("配送订单需要完整地址")
        if self.fulfillment == "dine_in" and not self.table_number: raise ValueError("堂食订单请填写桌号")
        if sum(i.quantity for i in self.items)>200: raise ValueError("单笔订单最多200件")
        return self

class OrderCreate(OrderDraft):
    request_key: str = Field(pattern=r"^[a-zA-Z0-9_-]{16,64}$")
    expected_total_cents: int = Field(ge=0, le=100000000, strict=True)

class StateChange(Input):
    status: Literal["ACCEPTED", "PREPARING", "READY", "DELIVERING", "COMPLETED", "CANCELLED"]
    expected_status: str = Field(max_length=24)
    reason: str = Field(default="", max_length=200)
    rider_id: int | None = Field(default=None, gt=0, strict=True)

class RiderInput(Input):
    name: str = Field(min_length=1, max_length=60)
    phone: str = Field(pattern=r"^1[3-9]\d{9}$")
    enabled: bool = True

class CouponInput(Input):
    title: str = Field(min_length=1, max_length=100)
    amount_cents: int = Field(gt=0, le=1000000, strict=True)
    minimum_cents: int = Field(default=0, ge=0, le=10000000, strict=True)
    quantity: int = Field(ge=1, le=100000, strict=True)
    starts_at: datetime
    expires_at: datetime
    birthday_only: bool = False
    enabled: bool = True
    @field_validator("starts_at", "expires_at")
    @classmethod
    def utc(cls,v):
        if v.tzinfo is None: raise ValueError("优惠券时间必须包含时区")
        return v.astimezone(timezone.utc).replace(tzinfo=None)
    @model_validator(mode="after")
    def valid_dates(self):
        if self.expires_at<=self.starts_at: raise ValueError("结束时间必须晚于开始时间")
        return self

class RewardInput(Input):
    title: str = Field(min_length=1, max_length=100)
    description: str = Field(default="", max_length=500)
    points_cost: int = Field(gt=0, le=1000000, strict=True)
    stock: int = Field(ge=0, le=100000, strict=True)
    enabled: bool = True

class TaskInput(Input):
    title: str = Field(min_length=1, max_length=100)
    kind: Literal["PROFILE", "ORDER_COUNT", "SPEND"]
    target: int = Field(ge=1, le=10000000, strict=True)
    points_reward: int = Field(ge=1, le=1000000, strict=True)
    enabled: bool = True

class Adjustment(Input):
    kind: Literal["POINTS", "WALLET"]
    delta: int = Field(ge=-1000000, le=1000000, strict=True)
    reason: str = Field(min_length=3, max_length=200)
    request_key: str = Field(pattern=r"^[a-zA-Z0-9_-]{16,64}$")

    @field_validator("delta")
    @classmethod
    def nonzero_delta(cls, value):
        if value == 0:
            raise ValueError("调整数量不能为0")
        return value

class RedemptionInput(Input):
    reward_id: int = Field(gt=0, strict=True)
    request_key: str = Field(pattern=r"^[a-zA-Z0-9_-]{16,64}$")

class RedemptionState(Input):
    status: Literal["REDEEMED", "CANCELLED"]

class EnabledInput(Input):
    enabled: bool
