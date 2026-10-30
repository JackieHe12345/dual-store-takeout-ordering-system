from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Store, StoreDomain
from app.models.enums import DomainType


def normalize_host(host: str) -> str:
    value = host.strip().lower().rstrip(".")
    if value.startswith("["):
        closing = value.find("]")
        return value[1:closing] if closing != -1 else value
    return value.split(":", 1)[0]


async def get_store_for_domain(
    session: AsyncSession, host: str, domain_type: DomainType | None = None
) -> Store | None:
    statement = (
        select(Store)
        .join(StoreDomain)
        .where(
            StoreDomain.domain == normalize_host(host),
            StoreDomain.enabled.is_(True),
            Store.enabled.is_(True),
        )
    )
    if domain_type is not None:
        statement = statement.where(StoreDomain.domain_type == domain_type)
    return await session.scalar(statement)


async def list_enabled_stores(session: AsyncSession) -> list[Store]:
    result = await session.scalars(select(Store).where(Store.enabled.is_(True)).order_by(Store.id))
    return list(result)
