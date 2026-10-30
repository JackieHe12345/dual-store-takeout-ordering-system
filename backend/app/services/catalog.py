from __future__ import annotations

from fastapi import HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Category, Dish
from app.repositories.catalog import get_category_in_store, get_dish_in_store
from app.schemas.catalog import CategoryCreate, CategoryUpdate, DishCreate, DishUpdate


async def commit_catalog_change(session: AsyncSession, message: str) -> None:
    try:
        await session.commit()
    except IntegrityError:
        await session.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, message) from None


async def create_category(
    session: AsyncSession, store_id: int, data: CategoryCreate
) -> Category:
    category = Category(store_id=store_id, dishes=[], **data.model_dump())
    session.add(category)
    await commit_catalog_change(session, "分类标识已存在，请使用不同标识")
    await session.refresh(category, attribute_names=["dishes"])
    return category


async def update_category(
    session: AsyncSession, store_id: int, category_id: int, data: CategoryUpdate
) -> Category:
    category = await get_category_in_store(session, category_id, store_id)
    if category is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "分类不存在")
    for key, value in data.model_dump(exclude_unset=True).items():
        setattr(category, key, value)
    await commit_catalog_change(session, "分类保存冲突，请刷新后重试")
    await session.refresh(category, attribute_names=["dishes"])
    return category


async def create_dish(session: AsyncSession, store_id: int, data: DishCreate) -> Dish:
    category = await get_category_in_store(session, data.category_id, store_id)
    if category is None:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "分类不属于当前门店")
    if data.original_price_cents is not None and data.original_price_cents < data.price_cents:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "原价不能低于现价")
    dish = Dish(store_id=store_id, **data.model_dump())
    session.add(dish)
    await commit_catalog_change(session, "菜品标识已存在，或分类已变更，请刷新后重试")
    await session.refresh(dish)
    return dish


async def update_dish(
    session: AsyncSession, store_id: int, dish_id: int, data: DishUpdate
) -> Dish:
    dish = await get_dish_in_store(session, dish_id, store_id)
    if dish is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "菜品不存在")
    updates = data.model_dump(exclude_unset=True)
    if "category_id" in updates:
        category = await get_category_in_store(session, updates["category_id"], store_id)
        if category is None:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "分类不属于当前门店")
    final_price = updates.get("price_cents", dish.price_cents)
    final_original = updates.get("original_price_cents", dish.original_price_cents)
    if final_original is not None and final_original < final_price:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "原价不能低于现价")
    for key, value in updates.items():
        setattr(dish, key, value)
    await commit_catalog_change(session, "菜品保存冲突，请刷新后重试")
    await session.refresh(dish)
    return dish
