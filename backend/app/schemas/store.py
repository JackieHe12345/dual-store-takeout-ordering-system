from __future__ import annotations

from decimal import Decimal

from pydantic import BaseModel

from app.models.enums import CoordinateSystem
from app.schemas.common import ORMModel


class StoreSummary(ORMModel):
    id: int
    slug: str
    name: str
    logo_url: str | None
    phone: str
    address: str


class StoreDetail(StoreSummary):
    enabled: bool
    latitude: Decimal
    longitude: Decimal
    coordinate_system: CoordinateSystem
    delivery_radius_meters: int


class StoreDomainRead(ORMModel):
    id: int
    store_id: int
    domain: str
    domain_type: str
    enabled: bool


class StoreCreate(BaseModel):
    slug: str
    name: str
    logo_url: str | None = None
    phone: str
    address: str
    latitude: Decimal
    longitude: Decimal
    coordinate_system: CoordinateSystem = CoordinateSystem.GCJ_02
    delivery_radius_meters: int = 5000
    enabled: bool = True
