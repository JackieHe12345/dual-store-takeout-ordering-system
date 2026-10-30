from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies.store_context import CustomerStore
from app.repositories.catalog import get_menu
from app.repositories.stores import list_enabled_stores
from app.schemas.catalog import MenuResponse
from app.schemas.store import StoreSummary

router = APIRouter(tags=["customer"])


@router.get("/stores", response_model=list[StoreSummary])
async def stores(session: Annotated[AsyncSession, Depends(get_db)]):
    return await list_enabled_stores(session)


@router.get("/menu", response_model=MenuResponse)
async def menu(store: CustomerStore, session: Annotated[AsyncSession, Depends(get_db)]):
    categories = await get_menu(session, store.id, public_only=True)
    return MenuResponse(store=StoreSummary.model_validate(store), categories=categories)
