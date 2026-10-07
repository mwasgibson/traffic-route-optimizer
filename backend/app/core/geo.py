"""Shared geospatial helpers."""

import math

from ..models.schemas import Coordinates

EARTH_RADIUS_KM = 6371.0


def haversine_distance_km(p1: Coordinates, p2: Coordinates) -> float:
    """Great-circle distance between two points in kilometres."""
    lat1, lon1 = math.radians(p1.lat), math.radians(p1.lon)
    lat2, lon2 = math.radians(p2.lat), math.radians(p2.lon)
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = (
        math.sin(dlat / 2) ** 2
        + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    )
    return EARTH_RADIUS_KM * 2 * math.asin(math.sqrt(a))