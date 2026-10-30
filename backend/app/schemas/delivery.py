from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

DeliveryCoordinateSystem = Literal["GCJ_02", "WGS_84", "BD_09"]


class Coordinates(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    coordinate_system: DeliveryCoordinateSystem = "GCJ_02"

    @field_validator("coordinate_system", mode="before")
    @classmethod
    def normalize_system(cls, value):
        return value.replace("-", "_") if isinstance(value, str) else value


class DeliveryFeeTier(BaseModel):
    model_config = ConfigDict(extra="forbid")
    up_to_meters: int = Field(gt=0, le=100000, strict=True)
    fee_cents: int = Field(ge=0, le=1000000, strict=True)


class DeliveryPlace(Coordinates):
    id: str = Field(min_length=1, max_length=80)
    title: str = Field(min_length=1, max_length=120)
    address: str = Field(max_length=500)
    city: str | None = Field(default=None, max_length=80)

    @field_validator("id", "title", "address", "city", mode="before")
    @classmethod
    def strip_place_text(cls, value):
        return value.strip() if isinstance(value, str) else value


class DeliverySettingsUpdate(Coordinates):
    address: str = Field(min_length=1, max_length=500)
    city: str | None = Field(max_length=80)
    delivery_radius_meters: int = Field(gt=0, le=100000, strict=True)
    delivery_location_confirmed: bool
    delivery_fee_tiers: list[DeliveryFeeTier] = Field(max_length=30)
    delivery_places: list[DeliveryPlace] | None = Field(default=None, max_length=100)

    @field_validator("address", "city", mode="before")
    @classmethod
    def strip_text(cls, value):
        return value.strip() if isinstance(value, str) else value

    @model_validator(mode="after")
    def validate_delivery_policy(self):
        bounds = [tier.up_to_meters for tier in self.delivery_fee_tiers]
        if bounds != sorted(set(bounds)):
            raise ValueError("配送费距离档位必须从小到大排列且不能重复")
        if bounds and bounds[-1] != self.delivery_radius_meters:
            raise ValueError("最后一个配送费档位必须等于最大配送距离")
        if self.delivery_location_confirmed and not self.city:
            raise ValueError("确认门店位置前请填写城市")
        if self.delivery_location_confirmed and self.latitude == 0 and self.longitude == 0:
            raise ValueError("请填写真实门店坐标后再确认位置")
        if self.delivery_places is not None:
            ids = [place.id for place in self.delivery_places]
            if len(set(ids)) != len(ids):
                raise ValueError("常送地址的标识不能重复")
            if any(place.latitude == 0 and place.longitude == 0 for place in self.delivery_places):
                raise ValueError("请填写常送地址的真实坐标")
        return self


class DeliverySettingsRead(Coordinates):
    store_id: int
    address: str
    city: str | None
    delivery_radius_meters: int
    delivery_location_confirmed: bool
    delivery_fee_tiers: list[DeliveryFeeTier]
    delivery_places: list[DeliveryPlace]
    provider_ready: bool
    distance_method: Literal["straight"] = "straight"


class DeliveryConfig(BaseModel):
    city: str | None
    radius_meters: int
    provider_ready: bool
    location_confirmed: bool
    fees_configured: bool
    places: list[DeliveryPlace]
    distance_method: Literal["straight"] = "straight"


class DeliveryPlaces(BaseModel):
    places: list[DeliveryPlace]


class DeliveryCheck(BaseModel):
    available: bool
    reason: str | None = None
    distance_meters: int | None = None
    within_range: bool | None = None
    radius_meters: int
    delivery_fee_cents: int | None = None
    distance_method: Literal["straight"] = "straight"
