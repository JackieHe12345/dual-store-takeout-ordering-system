from __future__ import annotations

from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Store
from app.models.enums import CoordinateSystem
from app.schemas.delivery import Coordinates, DeliveryCheck, DeliveryPlace, DeliverySettingsRead, DeliverySettingsUpdate
from app.utils.coordinates import straight_distance_meters, to_wgs84


def read_delivery_settings(store: Store) -> DeliverySettingsRead:
    return DeliverySettingsRead(
        store_id=store.id, address=store.address, city=store.delivery_city,
        latitude=float(store.latitude), longitude=float(store.longitude), coordinate_system=store.coordinate_system.name,
        delivery_radius_meters=store.delivery_radius_meters,
        delivery_location_confirmed=store.delivery_location_confirmed,
        delivery_fee_tiers=store.delivery_fee_tiers, delivery_places=store.delivery_places,
        provider_ready=True,
    )


async def update_delivery_settings(session: AsyncSession, store: Store, data: DeliverySettingsUpdate) -> DeliverySettingsRead:
    store.address = data.address
    store.delivery_city = data.city or None
    store.latitude = Decimal(str(data.latitude))
    store.longitude = Decimal(str(data.longitude))
    store.coordinate_system = CoordinateSystem[data.coordinate_system]
    store.delivery_radius_meters = data.delivery_radius_meters
    store.delivery_location_confirmed = data.delivery_location_confirmed
    store.delivery_fee_tiers = [tier.model_dump() for tier in data.delivery_fee_tiers]
    # Older clients omit this field; fee edits must preserve the saved places.
    if data.delivery_places is not None:
        store.delivery_places = [place.model_dump() for place in data.delivery_places]
    await session.commit()
    return read_delivery_settings(store)


def search_delivery_places(store: Store, keyword: str = "", city: str | None = None) -> list[DeliveryPlace]:
    needle = keyword.strip().casefold()
    city_filter = city.strip().casefold() if city else ""
    places = [DeliveryPlace.model_validate(place) for place in store.delivery_places]
    return [place for place in places
            if (not needle or needle in place.title.casefold() or needle in place.address.casefold())
            and (not city_filter or not place.city or city_filter == place.city.casefold())]


def describe_location(store: Store, coordinates: Coordinates) -> DeliveryPlace:
    point = to_wgs84(coordinates)
    return DeliveryPlace(
        id=f"gps:{point.latitude:.7f},{point.longitude:.7f}", title="已定位的收货点",
        address="", latitude=point.latitude, longitude=point.longitude,
        coordinate_system="WGS_84", city=store.delivery_city,
    )


async def check_delivery(store: Store, coordinates: Coordinates) -> DeliveryCheck:
    def unavailable(reason: str) -> DeliveryCheck:
        return DeliveryCheck(available=False, reason=reason, radius_meters=store.delivery_radius_meters)

    if not store.delivery_location_confirmed:
        return unavailable("门店正在确认配送位置，请联系门店")
    if not store.delivery_fee_tiers:
        return unavailable("门店正在设置配送费，请联系门店")
    try:
        distance = straight_distance_meters(
            Coordinates(latitude=float(store.latitude), longitude=float(store.longitude), coordinate_system=store.coordinate_system.name),
            coordinates,
        )
    except ValueError:
        return unavailable("无法识别地址坐标，请重新选择收货点")
    within = distance <= store.delivery_radius_meters
    fee = next((tier["fee_cents"] for tier in store.delivery_fee_tiers if distance <= tier["up_to_meters"]), None) if within else None
    if within and fee is None:
        return unavailable("门店正在设置配送费，请联系门店")
    return DeliveryCheck(
        available=True, reason=None if within else "该地址超出配送范围",
        distance_meters=distance, within_range=within, radius_meters=store.delivery_radius_meters,
        delivery_fee_cents=fee,
    )
