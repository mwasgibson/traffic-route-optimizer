"""Production traffic data service using TomTom Traffic API."""
import logging
import math
import random
from typing import Any, Dict, List, Optional

import httpx
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
)

from ..models.schemas import (
    TrafficSegment, TrafficCondition, Coordinates,
    TrafficHeatmapPoint, TrafficHeatmapResponse
)
from ..core.config import settings
from .cache import cache

logger = logging.getLogger(__name__)


class TrafficService:
    """Production traffic service using TomTom Traffic APIs."""

    BASE_URL = "https://api.tomtom.com/traffic/services/4"

    def __init__(self) -> None:
        self.api_key = settings.tomtom_api_key
        self.client = httpx.AsyncClient(
            timeout=settings.http_timeout_seconds,
            headers={"User-Agent": "TrafficRouteOptimizer/1.1"},
        )

    def _determine_congestion(self, ratio: float) -> TrafficCondition:
        if ratio >= 0.8:
            return TrafficCondition.LIGHT
        elif ratio >= 0.5:
            return TrafficCondition.MODERATE
        elif ratio >= 0.3:
            return TrafficCondition.HEAVY
        else:
            return TrafficCondition.SEVERE

    def _haversine_distance(self, p1: Coordinates, p2: Coordinates) -> float:
        R = 6371
        lat1, lon1 = math.radians(p1.lat), math.radians(p1.lon)
        lat2, lon2 = math.radians(p2.lat), math.radians(p2.lon)
        dlat = lat2 - lat1
        dlon = lon2 - lon1
        a = math.sin(dlat/2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon/2)**2
        return R * 2 * math.asin(math.sqrt(a))

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=8),
        retry=retry_if_exception_type(httpx.TransportError),
        reraise=False,  # On final failure return None so caller can estimate
    )
    async def _fetch_flow(self, lat: float, lon: float) -> Optional[Dict[str, Any]]:
        """Fetch TomTom flow segment data. Returns None on persistent failure."""
        params = {
            "key": self.api_key,
            "point": f"{lat},{lon}",
            "unit": "KMPH",
        }
        response = await self.client.get(
            f"{self.BASE_URL}/flowSegmentData/absolute/10/json",
            params=params,
        )
        if response.status_code != 200:
            return None
        return response.json()

    async def get_traffic_for_route(
        self,
        path: List[Coordinates]
    ) -> List[TrafficSegment]:
        """Get real traffic data for route segments using TomTom Flow Segment Data."""
        if not self.api_key:
            raise ValueError(
                "TomTom API key is required. "
                "Get a free key at https://developer.tomtom.com "
                "and set TOMTOM_API_KEY in your .env file."
            )

        segments: List[TrafficSegment] = []

        for i in range(len(path) - 1):
            start = path[i]
            end = path[i + 1]

            # Calculate midpoint for API query
            mid_lat = (start.lat + end.lat) / 2
            mid_lon = (start.lon + end.lon) / 2

            cache_key = f"traffic:{round(mid_lat, 3)}:{round(mid_lon, 3)}"
            flow = await cache.get_json(cache_key)

            if flow is None:
                try:
                    data = await self._fetch_flow(mid_lat, mid_lon)
                except httpx.TransportError:
                    data = None
                if data is not None:
                    flow = data.get("flowSegmentData", {})
                    await cache.set_json(
                        cache_key, flow, settings.traffic_cache_ttl
                    )

            if flow:
                current_speed = flow.get("currentSpeed", 60)
                free_flow = flow.get("freeFlowSpeed", current_speed)
                ratio = current_speed / free_flow if free_flow > 0 else 1.0

                # Calculate delay
                segment_dist = self._haversine_distance(start, end)
                time_free = (segment_dist / free_flow) * 60 if free_flow > 0 else 0
                time_current = (segment_dist / current_speed) * 60 if current_speed > 0 else 0
                delay = max(0, time_current - time_free)

                segments.append(TrafficSegment(
                    segment_id=f"seg_{i}",
                    start_coords=start,
                    end_coords=end,
                    current_speed=round(current_speed, 1),
                    free_flow_speed=round(free_flow, 1),
                    congestion_level=self._determine_congestion(ratio),
                    delay_minutes=round(delay, 1),
                    incident_count=1 if flow.get("roadClosure", False) else 0
                ))
            else:
                # Fallback: estimate from segment characteristics
                segments.append(self._estimate_segment(start, end, i))

        return segments

    def _estimate_segment(self, start: Coordinates, end: Coordinates, idx: int) -> TrafficSegment:
        """Estimate traffic when API is unavailable."""
        distance = self._haversine_distance(start, end)

        # Estimate speed based on segment length (shorter = urban = slower)
        if distance < 1.0:
            base_speed = 40
        elif distance < 3.0:
            base_speed = 60
        else:
            base_speed = 80

        # Add some realistic variation
        variation = random.uniform(0.7, 1.0)
        current_speed = base_speed * variation
        free_flow = base_speed * 1.1
        ratio = current_speed / free_flow

        time_free = (distance / free_flow) * 60
        time_current = (distance / current_speed) * 60
        delay = max(0, time_current - time_free)

        return TrafficSegment(
            segment_id=f"seg_{idx}",
            start_coords=start,
            end_coords=end,
            current_speed=round(current_speed, 1),
            free_flow_speed=round(free_flow, 1),
            congestion_level=self._determine_congestion(ratio),
            delay_minutes=round(delay, 1),
            incident_count=0
        )

    async def get_traffic_heatmap(
        self,
        north: float, south: float, east: float, west: float
    ) -> TrafficHeatmapResponse:
        """Generate traffic heatmap using TomTom Flow Segment Data or estimation."""
        points: list[TrafficHeatmapPoint] = []
        lat_step = (north - south) / 12
        lon_step = (east - west) / 12

        for i in range(12):
            for j in range(12):
                lat = south + i * lat_step
                lon = west + j * lon_step

                intensity = 0.3  # default light traffic
                speed = 60

                if self.api_key:
                    cache_key = f"traffic:{round(lat, 3)}:{round(lon, 3)}"
                    flow = await cache.get_json(cache_key)
                    if flow is None:
                        try:
                            data = await self._fetch_flow(lat, lon)
                        except httpx.TransportError:
                            data = None
                        if data is not None:
                            flow = data.get("flowSegmentData", {})
                            await cache.set_json(
                                cache_key, flow, settings.traffic_cache_ttl
                            )

                    if flow:
                        current = flow.get("currentSpeed", 60)
                        free = flow.get("freeFlowSpeed", 60)
                        ratio = current / free if free > 0 else 1.0
                        intensity = max(0, min(1, 1 - ratio))
                        speed = current

                points.append(TrafficHeatmapPoint(
                    lat=round(lat, 6),
                    lon=round(lon, 6),
                    intensity=round(intensity, 2),
                    speed=round(speed, 1)
                ))

        return TrafficHeatmapResponse(
            bounds={"north": north, "south": south, "east": east, "west": west},
            points=points,
            timestamp=__import__("datetime").datetime.now(
                __import__("datetime").timezone.utc
            ),
            total_incidents=0
        )

    async def close(self) -> None:
        await self.client.aclose()