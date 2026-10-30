from typing import Annotated

from fastapi import APIRouter, HTTPException, Query

from app.dependencies.store_context import CustomerStore
from app.models import Store
from app.schemas.delivery import Coordinates, DeliveryCheck, DeliveryConfig, DeliveryPlace, DeliveryPlaces
from app.services.delivery import check_delivery, describe_location, search_delivery_places

router = APIRouter(prefix="/delivery", tags=["delivery"])

Keyword = Annotated[str, Query(max_length=80)]
City = Annotated[str | None, Query(max_length=80)]


async def search_places(store: Store, keyword: str = "", city: str | None = None) -> DeliveryPlaces:
    return DeliveryPlaces(places=search_delivery_places(store, keyword, city))


@router.get("/config", response_model=DeliveryConfig)
async def delivery_config(store: CustomerStore):
    return DeliveryConfig(
        city=store.delivery_city, radius_meters=store.delivery_radius_meters,
        # Kept for older clients: the local distance engine is always ready.
        provider_ready=True, location_confirmed=store.delivery_location_confirmed,
        fees_configured=bool(store.delivery_fee_tiers), places=store.delivery_places,
    )


@router.get("/places", response_model=DeliveryPlaces)
async def delivery_places(store: CustomerStore, q: Keyword = "", city: City = None):
    return await search_places(store, q, city)


@router.post("/reverse", response_model=DeliveryPlace)
async def delivery_reverse(data: Coordinates, store: CustomerStore):
    try:
        return describe_location(store, data)
    except ValueError:
        raise HTTPException(422, "无法识别定位坐标，请重新定位") from None


@router.post("/check", response_model=DeliveryCheck)
async def delivery_check(data: Coordinates, store: CustomerStore):
    return await check_delivery(store, data)
