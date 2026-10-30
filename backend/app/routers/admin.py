from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.dependencies.auth import SuperAdmin, require_permission
from app.models import AdminUser, Role, Store
from app.models.enums import RoleCode
from app.repositories.catalog import get_menu
from app.schemas.auth import AdminUserCreate, AdminUserEnabledUpdate, UserRead
from app.schemas.catalog import (
    CategoryCreate,
    CategoryRead,
    CategoryUpdate,
    DishCreate,
    DishRead,
    DishUpdate,
    MenuResponse,
)
from app.schemas.media import ImageUploadRead
from app.schemas.store import StoreDetail, StoreSummary
from app.schemas.delivery import DeliveryPlaces, DeliverySettingsRead, DeliverySettingsUpdate
from app.services.delivery import read_delivery_settings, update_delivery_settings
from app.routers.delivery import City, Keyword, search_places
from app.services.catalog import create_category, create_dish, update_category, update_dish
from app.services.images import save_menu_image
from app.utils.security import hash_password
from app.routers.auth import serialize_user

router = APIRouter(prefix="/admin", tags=["central admin"])
MenuReader = Annotated[AdminUser, Depends(require_permission("menu:read"))]
MenuWriter = Annotated[AdminUser, Depends(require_permission("menu:write"))]


async def require_store(session: AsyncSession, store_id: int) -> Store:
    store = await session.get(Store, store_id)
    if store is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "门店不存在")
    return store


@router.get("/stores/{store_id}/delivery-settings", response_model=DeliverySettingsRead)
async def admin_delivery_settings(
    store_id: int, _: SuperAdmin, _permission: MenuReader,
    session: Annotated[AsyncSession, Depends(get_db)],
):
    return read_delivery_settings(await require_store(session, store_id))


@router.patch("/stores/{store_id}/delivery-settings", response_model=DeliverySettingsRead)
async def edit_admin_delivery_settings(
    store_id: int, data: DeliverySettingsUpdate, _: SuperAdmin, _permission: MenuWriter,
    session: Annotated[AsyncSession, Depends(get_db)],
):
    return await update_delivery_settings(session, await require_store(session, store_id), data)


@router.get("/stores/{store_id}/delivery-places", response_model=DeliveryPlaces)
async def admin_delivery_places(
    store_id: int, _: SuperAdmin, _permission: MenuReader,
    session: Annotated[AsyncSession, Depends(get_db)], q: Keyword = "", city: City = None,
):
    store = await require_store(session, store_id)
    return await search_places(store, q, city)


@router.get("/stores", response_model=list[StoreDetail])
async def admin_stores(
    _: SuperAdmin, session: Annotated[AsyncSession, Depends(get_db)]
):
    return list(await session.scalars(select(Store).order_by(Store.id)))


@router.get("/stores/{store_id}/menu", response_model=MenuResponse)
async def admin_store_menu(
    store_id: int,
    _: SuperAdmin,
    session: Annotated[AsyncSession, Depends(get_db)],
):
    store = await require_store(session, store_id)
    categories = await get_menu(session, store_id, public_only=False)
    return MenuResponse(store=StoreSummary.model_validate(store), categories=categories)


@router.post("/stores/{store_id}/categories", response_model=CategoryRead, status_code=status.HTTP_201_CREATED)
async def add_store_category(
    store_id: int,
    data: CategoryCreate,
    _: SuperAdmin,
    session: Annotated[AsyncSession, Depends(get_db)],
):
    await require_store(session, store_id)
    return await create_category(session, store_id, data)


@router.patch("/stores/{store_id}/categories/{category_id}", response_model=CategoryRead)
async def edit_store_category(
    store_id: int,
    category_id: int,
    data: CategoryUpdate,
    _: SuperAdmin,
    session: Annotated[AsyncSession, Depends(get_db)],
):
    await require_store(session, store_id)
    return await update_category(session, store_id, category_id, data)


@router.post("/stores/{store_id}/dishes", response_model=DishRead, status_code=status.HTTP_201_CREATED)
async def add_store_dish(
    store_id: int,
    data: DishCreate,
    _: SuperAdmin,
    session: Annotated[AsyncSession, Depends(get_db)],
):
    await require_store(session, store_id)
    return await create_dish(session, store_id, data)


@router.patch("/stores/{store_id}/dishes/{dish_id}", response_model=DishRead)
async def edit_store_dish(
    store_id: int,
    dish_id: int,
    data: DishUpdate,
    _: SuperAdmin,
    session: Annotated[AsyncSession, Depends(get_db)],
):
    await require_store(session, store_id)
    return await update_dish(session, store_id, dish_id, data)


@router.post("/stores/{store_id}/images", response_model=ImageUploadRead, status_code=status.HTTP_201_CREATED)
async def upload_store_image(
    store_id: int,
    _: SuperAdmin,
    session: Annotated[AsyncSession, Depends(get_db)],
    file: Annotated[UploadFile, File()],
):
    await require_store(session, store_id)
    return await save_menu_image(file)


@router.get("/users", response_model=list[UserRead])
async def admin_users(
    _: SuperAdmin, session: Annotated[AsyncSession, Depends(get_db)]
):
    users = list(
        await session.scalars(
            select(AdminUser)
            .options(selectinload(AdminUser.role).selectinload(Role.permissions))
            .order_by(AdminUser.id)
        )
    )
    return [serialize_user(user) for user in users]


@router.post("/users", response_model=UserRead, status_code=status.HTTP_201_CREATED)
async def add_admin_user(
    data: AdminUserCreate,
    _: SuperAdmin,
    session: Annotated[AsyncSession, Depends(get_db)],
):
    role = await session.scalar(
        select(Role).where(Role.code == data.role_code).options(selectinload(Role.permissions))
    )
    if role is None:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "角色不存在")
    if role.code == RoleCode.SUPER_ADMIN and data.store_id is not None:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "总管理员不能绑定门店")
    if role.code != RoleCode.SUPER_ADMIN:
        if data.store_id is None or await session.get(Store, data.store_id) is None:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "门店角色必须绑定有效门店")
    user = AdminUser(
        username=data.username,
        password_hash=hash_password(data.password),
        display_name=data.display_name,
        role=role,
        store_id=data.store_id,
        enabled=data.enabled,
    )
    session.add(user)
    try:
        await session.commit()
    except IntegrityError:
        await session.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, "用户名已存在") from None
    await session.refresh(user)
    return serialize_user(user)


@router.patch("/users/{user_id}/enabled", response_model=UserRead)
async def set_admin_user_enabled(
    user_id: int,
    data: AdminUserEnabledUpdate,
    current: SuperAdmin,
    session: Annotated[AsyncSession, Depends(get_db)],
):
    if user_id == current.id and not data.enabled:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "不能禁用当前登录账号")
    user = await session.scalar(
        select(AdminUser)
        .where(AdminUser.id == user_id)
        .options(selectinload(AdminUser.role).selectinload(Role.permissions))
    )
    if user is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "账号不存在")
    user.enabled = data.enabled
    await session.commit()
    return serialize_user(user)
