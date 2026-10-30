"""Local coordinate normalization and spherical straight-line distances.

GCJ/BD transform formulas are adapted from wandergis/coordtransform (MIT):
https://github.com/wandergis/coordtransform ; see THIRD_PARTY_NOTICES.md.
These are approximate local transforms, not an external map lookup. The inverse
is iterated rather than using the less accurate one-step GCJ approximation.
"""

import math

from app.schemas.delivery import Coordinates

EARTH_MEAN_RADIUS_METERS = 6371008.8
_GCJ_A = 6378245.0
_GCJ_EE = 0.00669342162296594323
_X_PI = math.pi * 3000 / 180


def _outside_gcj_region(latitude: float, longitude: float) -> bool:
    # This commonly used historical GCJ bounding box is an approximation,
    # not a national border polygon.
    return not (72.004 <= longitude <= 137.8347 and 0.8293 <= latitude <= 55.8271)


def wgs84_to_gcj02(latitude: float, longitude: float) -> tuple[float, float]:
    if _outside_gcj_region(latitude, longitude):
        return latitude, longitude
    x, y = longitude - 105, latitude - 35
    dlat = -100 + 2*x + 3*y + 0.2*y*y + 0.1*x*y + 0.2*math.sqrt(abs(x))
    dlng = 300 + x + 2*y + 0.1*x*x + 0.1*x*y + 0.1*math.sqrt(abs(x))
    common = (20*math.sin(6*x*math.pi) + 20*math.sin(2*x*math.pi)) * 2/3
    dlat += common + (20*math.sin(y*math.pi) + 40*math.sin(y*math.pi/3))*2/3
    dlat += (160*math.sin(y*math.pi/12) + 320*math.sin(y*math.pi/30))*2/3
    dlng += common + (20*math.sin(x*math.pi) + 40*math.sin(x*math.pi/3))*2/3
    dlng += (150*math.sin(x*math.pi/12) + 300*math.sin(x*math.pi/30))*2/3
    rad_lat = math.radians(latitude)
    magic = 1 - _GCJ_EE * math.sin(rad_lat)**2
    dlat = dlat * 180 / ((_GCJ_A*(1-_GCJ_EE)/(magic*math.sqrt(magic)))*math.pi)
    dlng = dlng * 180 / ((_GCJ_A/math.sqrt(magic))*math.cos(rad_lat)*math.pi)
    return latitude + dlat, longitude + dlng


def gcj02_to_wgs84(latitude: float, longitude: float) -> tuple[float, float]:
    if _outside_gcj_region(latitude, longitude):
        return latitude, longitude
    candidate_lat, candidate_lng = latitude, longitude
    for _ in range(30):
        transformed_lat, transformed_lng = wgs84_to_gcj02(candidate_lat, candidate_lng)
        dlat, dlng = transformed_lat - latitude, transformed_lng - longitude
        candidate_lat -= dlat
        candidate_lng -= dlng
        if max(abs(dlat), abs(dlng)) < 1e-10:
            return candidate_lat, candidate_lng
    # The reference bounding box has discontinuities near its edges. Refuse a
    # nonconvergent inverse rather than billing using mixed coordinate systems.
    raise ValueError("Coordinate conversion did not converge")


def bd09_to_gcj02(latitude: float, longitude: float) -> tuple[float, float]:
    x, y = longitude - 0.0065, latitude - 0.006
    radius = math.hypot(x, y) - 0.00002 * math.sin(y * _X_PI)
    angle = math.atan2(y, x) - 0.000003 * math.cos(x * _X_PI)
    return radius * math.sin(angle), radius * math.cos(angle)


def to_wgs84(coordinates: Coordinates) -> Coordinates:
    latitude, longitude = coordinates.latitude, coordinates.longitude
    if coordinates.coordinate_system == "BD_09":
        latitude, longitude = bd09_to_gcj02(latitude, longitude)
    if coordinates.coordinate_system in ("GCJ_02", "BD_09"):
        latitude, longitude = gcj02_to_wgs84(latitude, longitude)
    return Coordinates(latitude=latitude, longitude=longitude, coordinate_system="WGS_84")


def straight_distance_meters(start: Coordinates, destination: Coordinates) -> int:
    origin, target = to_wgs84(start), to_wgs84(destination)
    lat1, lat2 = math.radians(origin.latitude), math.radians(target.latitude)
    dlat, dlng = lat2 - lat1, math.radians(target.longitude - origin.longitude)
    a = math.sin(dlat/2)**2 + math.cos(lat1)*math.cos(lat2)*math.sin(dlng/2)**2
    a = min(1.0, max(0.0, a))
    distance = EARTH_MEAN_RADIUS_METERS * 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
    # Floating error must not turn an exact whole-meter threshold into +1 m.
    nearest = round(distance)
    if math.isclose(distance, nearest, rel_tol=0, abs_tol=1e-7):
        distance = float(nearest)
    return math.ceil(distance)
