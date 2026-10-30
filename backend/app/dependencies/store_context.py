from __future__ import annotations

from typing import Annotated

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import Store
from app.models.enums import DomainType
from app.repositories.stores import get_store_for_domain

DBSession = Annotated[AsyncSession, Depends(get_db)]


async def get_customer_store(request: Request, session: DBSession) -> Store:
    store = await get_store_for_domain(session, request.headers.get("host", ""), DomainType.CUSTOMER)
    if store is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "当前域名未绑定可用顾客门店")
    return store


CustomerStore = Annotated[Store, Depends(get_customer_store)]
