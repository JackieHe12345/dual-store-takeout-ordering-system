from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies.auth import ScopedStaffUser, require_permission
from app.models import AdminUser
from app.repositories.catalog import get_menu
from app.schemas.catalog import (
    CategoryCreate,
    CategoryRead,
    CategoryUpdate,
    DishCreate,
    DishRead,
    DishUpdate,
    MenuResponse,
)
from app.schemas.store import StoreSummary
from app.schemas.media import ImageUploadRead
from app.schemas.delivery import DeliveryPlaces, DeliverySettingsRead, DeliverySettingsUpdate
from app.services.delivery import read_delivery_settings, update_delivery_settings
from app.routers.delivery import City, Keyword, search_places
from app.services.catalog import create_category, create_dish, update_category, update_dish
from app.services.images import save_menu_image

router = APIRouter(prefix="/staff", tags=["staff"])

MenuReader = Annotated[AdminUser, Depends(require_permission("menu:read"))]
MenuWriter = Annotated[AdminUser, Depends(require_permission("menu:write"))]


def scoped_store_id(user: AdminUser) -> int:
    if user.store_id is None:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "门店接口不接受跨店账号")
    return user.store_id


@router.get("/delivery-settings", response_model=DeliverySettingsRead)
async def staff_delivery_settings(scoped_user: ScopedStaffUser, _: MenuReader):
    return read_delivery_settings(scoped_user.store)


@router.patch("/delivery-settings", response_model=DeliverySettingsRead)
async def edit_staff_delivery_settings(
    data: DeliverySettingsUpdate,
    scoped_user: ScopedStaffUser,
    _: MenuWriter,
    session: Annotated[AsyncSession, Depends(get_db)],
):
    return await update_delivery_settings(session, scoped_user.store, data)


@router.get("/delivery-places", response_model=DeliveryPlaces)
async def staff_delivery_places(scoped_user: ScopedStaffUser, _: MenuReader, q: Keyword = "", city: City = None):
    return await search_places(scoped_user.store, q, city)


@router.get("/menu", response_model=MenuResponse)
async def staff_menu(
    scoped_user: ScopedStaffUser,
    _: MenuReader,
    session: Annotated[AsyncSession, Depends(get_db)],
):
    store_id = scoped_store_id(scoped_user)
    categories = await get_menu(session, store_id, public_only=False)
    return MenuResponse(store=StoreSummary.model_validate(scoped_user.store), categories=categories)


@router.post("/categories", response_model=CategoryRead, status_code=status.HTTP_201_CREATED)
async def add_category(
    data: CategoryCreate,
    scoped_user: ScopedStaffUser,
    _: MenuWriter,
    session: Annotated[AsyncSession, Depends(get_db)],
):
    return await create_category(session, scoped_store_id(scoped_user), data)


@router.patch("/categories/{category_id}", response_model=CategoryRead)
async def edit_category(
    category_id: int,
    data: CategoryUpdate,
    scoped_user: ScopedStaffUser,
    _: MenuWriter,
    session: Annotated[AsyncSession, Depends(get_db)],
):
    return await update_category(session, scoped_store_id(scoped_user), category_id, data)


@router.post("/dishes", response_model=DishRead, status_code=status.HTTP_201_CREATED)
async def add_dish(
    data: DishCreate,
    scoped_user: ScopedStaffUser,
    _: MenuWriter,
    session: Annotated[AsyncSession, Depends(get_db)],
):
    return await create_dish(session, scoped_store_id(scoped_user), data)


@router.patch("/dishes/{dish_id}", response_model=DishRead)
async def edit_dish(
    dish_id: int,
    data: DishUpdate,
    scoped_user: ScopedStaffUser,
    _: MenuWriter,
    session: Annotated[AsyncSession, Depends(get_db)],
):
    return await update_dish(session, scoped_store_id(scoped_user), dish_id, data)


@router.post("/images", response_model=ImageUploadRead, status_code=status.HTTP_201_CREATED)
async def upload_image(
    scoped_user: ScopedStaffUser,
    _: MenuWriter,
    file: Annotated[UploadFile, File()],
):
    scoped_store_id(scoped_user)
    return await save_menu_image(file)
