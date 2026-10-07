"""Traffic data service using TomTom Traffic API."""
import logging
import math
import random
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, cast

import httpx
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from ..core.config import settings
from .cache import cache
from ..core.constants import MAX_TRAFFIC_SAMPLES_PER_ROUTE
from ..core.geo import haversine_distance_km
from ..models.schemas import (
    Coordinates,
    TrafficCondition,
    TrafficHeatmapPoint,
    TrafficHeatmapResponse,
    TrafficSegment,
)

logger = logging.getLogger(__name__)


class TrafficService:
    """Traffic service backed by TomTom Flow Segment Data."""

    BASE_URL = "https://api.tomtom.com/traffic/services/4"

    def __init__(self, client: Optional[httpx.AsyncClient] = None):
        self.api_key = settings.tomtom_api_key
        self._owns_client = client is None
        self.client = client or httpx.AsyncClient(timeout=15.0)

    def _determine_congestion(self, ratio: float) -> TrafficCondition:
        if ratio >= 0.8:
            return TrafficCondition.LIGHT
        if ratio >= 0.5:
            return TrafficCondition.MODERATE
        if ratio >= 0.3:
            return TrafficCondition.HEAVY
        return TrafficCondition.SEVERE

    def _sample_indices(self, path_len: int) -> List[int]:
        """Downsample long paths to limit TomTom calls."""
        segment_count = max(0, path_len - 1)
        if segment_count <= MAX_TRAFFIC_SAMPLES_PER_ROUTE:
            return list(range(segment_count))
        step = segment_count / MAX_TRAFFIC_SAMPLES_PER_ROUTE
        return sorted(
            {
                min(int(i * step), segment_count - 1)
                for i in range(MAX_TRAFFIC_SAMPLES_PER_ROUTE)
            }
        )

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=8),
        retry=retry_if_exception_type(httpx.TransportError),
        reraise=True,
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

    async def _get_flow_data(
        self, cache_key: str, lat: float, lon: float
    ) -> Optional[Dict[str, Any]]:
        cached = await cache.get_json(cache_key)
        if isinstance(cached, dict):
            return cast(Dict[str, Any], cached)

        try:
            data = await self._fetch_flow(lat, lon)
        except httpx.TransportError as exc:
            logger.debug("TomTom request failed at (%s, %s): %s", lat, lon, exc)
            return None

        if data is None:
            return None
        flow = data.get("flowSegmentData")
        if not isinstance(flow, dict):
            return None

        typed_flow = cast(Dict[str, Any], flow)
        await cache.set_json(cache_key, typed_flow, settings.traffic_cache_ttl)
        return typed_flow

    @staticmethod
    def _flow_speeds(flow: Dict[str, Any]) -> Optional[tuple[float, float]]:
        try:
            current_speed = float(flow.get("currentSpeed", 60))
            free_flow_speed = float(flow.get("freeFlowSpeed", current_speed))
        except (TypeError, ValueError):
            logger.warning("TomTom returned invalid speed values: %r", flow)
            return None

        if (
            not math.isfinite(current_speed)
            or not math.isfinite(free_flow_speed)
            or current_speed < 0
            or free_flow_speed < 0
        ):
            logger.warning("TomTom returned out-of-range speed values: %r", flow)
            return None
        return current_speed, free_flow_speed

    async def get_traffic_for_route(
        self,
        path: List[Coordinates],
    ) -> List[TrafficSegment]:
        """Get traffic data for route segments (sampled on long paths)."""
        if not self.api_key:
            raise ValueError(
                "TomTom API key is required. "
                "Get a free key at https://developer.tomtom.com "
                "and set TOMTOM_API_KEY in your .env file."
            )

        if len(path) < 2:
            return []

        segments: List[TrafficSegment] = []
        for i in self._sample_indices(len(path)):
            start = path[i]
            end = path[i + 1]
            mid_lat = (start.lat + end.lat) / 2
            mid_lon = (start.lon + end.lon) / 2

            cache_key = f"traffic:{round(mid_lat, 3)}:{round(mid_lon, 3)}"
            flow = await self._get_flow_data(cache_key, mid_lat, mid_lon)
            speeds = self._flow_speeds(flow) if flow is not None else None

            if flow is not None and speeds is not None:
                current_speed, free_flow = speeds
                ratio = current_speed / free_flow if free_flow > 0 else 1.0

                # Calculate delay
                segment_dist = haversine_distance_km(start, end)
                time_free = (segment_dist / free_flow) * 60 if free_flow > 0 else 0.0
                time_current = (
                    (segment_dist / current_speed) * 60
                    if current_speed > 0
                    else 0.0
                )
                delay = max(0.0, time_current - time_free)

                segments.append(
                    TrafficSegment(
                        segment_id=f"seg_{i}",
                        start_coords=start,
                        end_coords=end,
                        current_speed=round(current_speed, 1),
                        free_flow_speed=round(free_flow, 1),
                        congestion_level=self._determine_congestion(ratio),
                        delay_minutes=round(delay, 1),
                        incident_count=1 if flow.get("roadClosure", False) else 0,
                    )
                )
            else:
                segments.append(self._estimate_segment(start, end, i))

        return segments

    def _estimate_segment(
        self, start: Coordinates, end: Coordinates, idx: int
    ) -> TrafficSegment:
        """Estimate traffic when API is unavailable for a segment."""
        distance = haversine_distance_km(start, end)
        if distance < 1.0:
            base_speed = 40.0
        elif distance < 3.0:
            base_speed = 60.0
        else:
            base_speed = 80.0

        # Add some realistic variation
        variation = random.uniform(0.7, 1.0)
        current_speed = base_speed * variation
        free_flow = base_speed * 1.1
        ratio = current_speed / free_flow
        time_free = (distance / free_flow) * 60
        time_current = (distance / current_speed) * 60
        delay = max(0.0, time_current - time_free)

        return TrafficSegment(
            segment_id=f"seg_{idx}",
            start_coords=start,
            end_coords=end,
            current_speed=round(current_speed, 1),
            free_flow_speed=round(free_flow, 1),
            congestion_level=self._determine_congestion(ratio),
            delay_minutes=round(delay, 1),
            incident_count=0,
        )

    async def get_traffic_heatmap(
        self, north: float, south: float, east: float, west: float
    ) -> TrafficHeatmapResponse:
        """Generate a coarse traffic heatmap for a bounding box."""
        points: List[TrafficHeatmapPoint] = []
        lat_step = (north - south) / 12 if north != south else 0.01
        lon_step = (east - west) / 12 if east != west else 0.01

        for i in range(12):
            for j in range(12):
                lat = south + i * lat_step
                lon = west + j * lon_step

                intensity = 0.3  # default light traffic
                speed = 60

                if self.api_key:
                    cache_key = f"traffic:{round(lat, 3)}:{round(lon, 3)}"
                    flow = await self._get_flow_data(cache_key, lat, lon)
                    speeds = self._flow_speeds(flow) if flow is not None else None
                    if speeds is not None:
                        current_speed, free_flow_speed = speeds
                        ratio = (
                            current_speed / free_flow_speed
                            if free_flow_speed > 0
                            else 1.0
                        )
                        intensity = max(0.0, min(1.0, 1.0 - ratio))
                        speed = current_speed
                points.append(
                    TrafficHeatmapPoint(
                        lat=round(lat, 6),
                        lon=round(lon, 6),
                        intensity=round(intensity, 2),
                        speed=round(speed, 1),
                    )
                )

        return TrafficHeatmapResponse(
            bounds={
                "north": north,
                "south": south,
                "east": east,
                "west": west,
            },
            points=points,
            timestamp=datetime.now(timezone.utc),
            total_incidents=0,
        )

    async def close(self) -> None:
        if self._owns_client:
            await self.client.aclose()