from __future__ import annotations

from pydantic import BaseModel, Field, field_validator

from app.schemas.common import ORMModel
from app.schemas.store import StoreSummary

MAX_DB_INTEGER = 2_147_483_647


class DishRead(ORMModel):
    id: int
    category_id: int
    name: str
    slug: str
    description: str | None
    image_url: str | None
    price_cents: int
    original_price_cents: int | None
    monthly_sales: int
    stock: int | None
    requires_options: bool
    sold_out: bool
    enabled: bool
    sort_order: int


class CategoryRead(ORMModel):
    id: int
    name: str
    slug: str
    description: str | None
    icon: str | None
    sort_order: int
    enabled: bool
    dishes: list[DishRead]


class MenuResponse(BaseModel):
    store: StoreSummary
    categories: list[CategoryRead]


class CategoryCreate(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    slug: str = Field(pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$", max_length=80)
    description: str | None = Field(default=None, max_length=300)
    icon: str | None = Field(default=None, max_length=80)
    sort_order: int = Field(default=0, ge=-MAX_DB_INTEGER - 1, le=MAX_DB_INTEGER)
    enabled: bool = True


class CategoryUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=80)
    description: str | None = Field(default=None, max_length=300)
    icon: str | None = Field(default=None, max_length=80)
    sort_order: int | None = Field(default=None, ge=-MAX_DB_INTEGER - 1, le=MAX_DB_INTEGER)
    enabled: bool | None = None

    @field_validator("name", "sort_order", "enabled", mode="before")
    @classmethod
    def reject_null_required_fields(cls, value):
        if value is None:
            raise ValueError("此字段不能设置为空")
        return value


class DishCreate(BaseModel):
    category_id: int
    name: str = Field(min_length=1, max_length=120)
    slug: str = Field(pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$", max_length=100)
    description: str | None = None
    image_url: str | None = Field(default=None, max_length=500)
    price_cents: int = Field(ge=0, le=MAX_DB_INTEGER)
    original_price_cents: int | None = Field(default=None, ge=0, le=MAX_DB_INTEGER)
    monthly_sales: int = Field(default=0, ge=0, le=MAX_DB_INTEGER)
    stock: int | None = Field(default=None, ge=0, le=MAX_DB_INTEGER)
    requires_options: bool = False
    sold_out: bool = False
    enabled: bool = True
    sort_order: int = Field(default=0, ge=-MAX_DB_INTEGER - 1, le=MAX_DB_INTEGER)


class DishUpdate(BaseModel):
    category_id: int | None = None
    name: str | None = Field(default=None, min_length=1, max_length=120)
    description: str | None = None
    image_url: str | None = Field(default=None, max_length=500)
    price_cents: int | None = Field(default=None, ge=0, le=MAX_DB_INTEGER)
    original_price_cents: int | None = Field(default=None, ge=0, le=MAX_DB_INTEGER)
    monthly_sales: int | None = Field(default=None, ge=0, le=MAX_DB_INTEGER)
    stock: int | None = Field(default=None, ge=0, le=MAX_DB_INTEGER)
    requires_options: bool | None = None
    sold_out: bool | None = None
    enabled: bool | None = None
    sort_order: int | None = Field(default=None, ge=-MAX_DB_INTEGER - 1, le=MAX_DB_INTEGER)

    @field_validator(
        "category_id", "name", "price_cents", "monthly_sales", "requires_options",
        "sold_out", "enabled", "sort_order", mode="before",
    )
    @classmethod
    def reject_null_required_fields(cls, value):
        if value is None:
            raise ValueError("此字段不能设置为空")
        return value
