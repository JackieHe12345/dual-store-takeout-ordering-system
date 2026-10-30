from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models import Category, Dish


async def get_menu(
    session: AsyncSession, store_id: int, *, public_only: bool = True
) -> list[Category]:
    dish_filters = [Dish.store_id == store_id]
    category_filters = [Category.store_id == store_id]
    if public_only:
        dish_filters.extend(
            [Dish.enabled.is_(True)]
        )
        category_filters.append(Category.enabled.is_(True))

    statement = (
        select(Category)
        .where(*category_filters)
        .options(
            selectinload(
                Category.dishes.and_(*dish_filters)
            )
        )
        .order_by(Category.sort_order, Category.id)
    )
    categories = list(await session.scalars(statement))
    for category in categories:
        category.dishes.sort(key=lambda dish: (dish.sort_order, dish.id))
    return categories


async def get_category_in_store(
    session: AsyncSession, category_id: int, store_id: int
) -> Category | None:
    return await session.scalar(
        select(Category).where(Category.id == category_id, Category.store_id == store_id)
    )


async def get_dish_in_store(
    session: AsyncSession, dish_id: int, store_id: int
) -> Dish | None:
    return await session.scalar(select(Dish).where(Dish.id == dish_id, Dish.store_id == store_id))
