"""Multi-factor route optimization engine (OSRM geometry + live traffic/weather)."""
import logging
import hashlib
import math
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

import httpx
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
)

from ..models.schemas import (
    Coordinates, RouteAlternative, RouteMetrics, RouteOptimizationResponse,
    TrafficCondition, WeatherCondition, TrafficSegment, TransportMode,
    NavigationInstruction,
)
from ..core.config import settings
from ..core.constants import (
    DISTANCE_SCORE_ANCHOR_KM,
    FUEL_RATES_L_PER_100KM,
    FUEL_SCORE_ANCHOR_L,
    TIME_SCORE_ANCHOR_MIN,
    WEATHER_WEIGHT_BONUS,
)
from ..core.geo import haversine_distance_km
from ..models.schemas import (
    Coordinates,
    RouteAlternative,
    RouteMetrics,
    RouteOptimizationResponse,
    TrafficCondition,
    TrafficSegment,
    VehicleType,
    WeatherCondition,
)
from .traffic_service import TrafficService
from .cache import cache
from .weather_service import WeatherService

logger = logging.getLogger(__name__)


class RouteOptimizer:
    """Production multi-factor route optimization engine.

    Supports multi-stop trips (ordered waypoints), transport-mode-aware
    routing (driving via OSRM, cycling/walking via OpenRouteService), and
    turn-by-turn navigation instructions parsed from the routing response.
    """

    OSRM_URL = "http://router.project-osrm.org/route/v1"
    ORS_URL = "https://api.openrouteservice.org/v2/directions"

    # OSRM / ORS profile mapping by transport mode
    ORS_PROFILES = {
        TransportMode.DRIVING: "driving-car",
        TransportMode.CYCLING: "cycling-regular",
        TransportMode.WALKING: "foot-walking",
    }

    # Fuel consumption rates (L/100km) by vehicle type
    FUEL_RATES = {
        "car": 6.5,
        "motorcycle": 3.5,
        "truck": 25.0,
        "bus": 35.0
    }

    CO2_PER_LITER = 2.31

    def __init__(
        self,
        weather_service: Optional[WeatherService] = None,
        traffic_service: Optional[TrafficService] = None,
        routing_client: Optional[httpx.AsyncClient] = None,
    ):
        self.weather_service = weather_service or WeatherService()
        self.traffic_service = traffic_service or TrafficService()
        self._owns_routing_client = routing_client is None
        self.routing_client = routing_client or httpx.AsyncClient(timeout=30.0)

    def _osrm_exclude_param(
        self, avoid_tolls: bool, avoid_highways: bool
    ) -> Optional[str]:
        """Build OSRM `exclude` query value from avoid flags."""
        parts: List[str] = []
        if avoid_tolls:
            parts.append("toll")
        if avoid_highways:
            parts.append("motorway")
        return ",".join(parts) if parts else None

    def _route_cache_key(
        self,
        origin: Coordinates,
        destination: Coordinates,
        waypoints: List[Coordinates],
        mode: TransportMode,
    ) -> str:
        raw = (
            f"{origin.lat},{origin.lon};"
            + ";".join(f"{w.lat},{w.lon}" for w in waypoints)
            + f";{destination.lat},{destination.lon};{mode.value}"
        )
        digest = hashlib.sha256(raw.encode()).hexdigest()[:24]
        return f"route:{mode.value}:{digest}"

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=8),
        retry=retry_if_exception_type(httpx.TransportError),
        reraise=False,
    )
    async def _request_osrm(
        self,
        origin: Coordinates,
        destination: Coordinates,
        waypoints: List[Coordinates],
        avoid_tolls: bool = False,
        avoid_highways: bool = False,
    ) -> Optional[Dict[str, Any]]:
        """Query OSRM for real road-following routes (driving profile)."""
        all_points = [origin, *waypoints, destination]
        coords = ";".join(f"{p.lon},{p.lat}" for p in all_points)
        url = f"{self.OSRM_URL}/driving/{coords}"
        params: Dict[str, Any] = {
            "overview": "full",
            "geometries": "geojson",
            "steps": "true",
            "alternatives": "3" if not waypoints else "false",
        }
        exclude = self._osrm_exclude_param(avoid_tolls, avoid_highways)
        if exclude:
            params["exclude"] = exclude
        try:
            response = await self.routing_client.get(
                url,
                params=params,
                timeout=15.0,
            )
        except httpx.HTTPError as exc:
            logger.warning("OSRM request failed: %s", exc)
            return None
        if response.status_code != 200:
            logger.warning("OSRM returned %s for route request", response.status_code)
            return None
        return response.json()

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=8),
        retry=retry_if_exception_type(httpx.TransportError),
        reraise=False,
    )
    async def _request_ors(
        self,
        origin: Coordinates,
        destination: Coordinates,
        waypoints: List[Coordinates],
        mode: TransportMode,
    ) -> Optional[Dict[str, Any]]:
        """Query OpenRouteService for non-driving profiles (or as ORS fallback)."""
        if not settings.openroute_api_key:
            return None

        profile = self.ORS_PROFILES.get(mode, "driving-car")
        url = f"{self.ORS_URL}/{profile}"

        # ORS expects [lon, lat] pairs
        coordinates = [
            [origin.lon, origin.lat],
            *[[w.lon, w.lat] for w in waypoints],
            [destination.lon, destination.lat],
        ]

        response = await self.routing_client.post(
            url,
            json={"coordinates": coordinates},
            headers={"Authorization": settings.openroute_api_key},
            timeout=20.0,
        )
        if response.status_code != 200:
            return None
        return response.json()

    @staticmethod
    def _parse_osrm_instructions(route_item: Dict[str, Any]) -> List[NavigationInstruction]:
        """Parse OSRM steps into turn-by-turn navigation instructions."""
        instructions: List[NavigationInstruction] = []
        for leg in route_item.get("legs", []):
            for step in leg.get("steps", []):
                maneuver = step.get("maneuver", {})
                m_type = maneuver.get("type", "continue")
                modifier = maneuver.get("modifier")
                street = step.get("name") or None

                # Build a human-readable instruction
                phrase = m_type.replace("_", " ")
                if modifier:
                    phrase = f"{modifier} {phrase}"
                text = phrase.capitalize()
                if street:
                    text += f" onto {street}"

                instructions.append(NavigationInstruction(
                    instruction=text,
                    distance_m=round(step.get("distance", 0), 1),
                    duration_s=round(step.get("duration", 0), 1),
                    maneuver_type=m_type,
                    street_name=street,
                ))
        return instructions

    @staticmethod
    def _parse_ors_instructions(feature: Dict[str, Any]) -> List[NavigationInstruction]:
        """Parse OpenRouteService steps into turn-by-turn navigation instructions."""
        instructions: List[NavigationInstruction] = []
        props = feature.get("properties", {})
        for segment in props.get("segments", []):
            for step in segment.get("steps", []):
                instructions.append(NavigationInstruction(
                    instruction=step.get("instruction", "Continue"),
                    distance_m=round(step.get("distance", 0), 1),
                    duration_s=round(step.get("duration", 0), 1),
                    maneuver_type=str(step.get("type", "continue")),
                    street_name=step.get("name") or None,
                ))
        return instructions

    async def _get_real_routes(
        self,
        origin: Coordinates,
        destination: Coordinates,
        waypoints: List[Coordinates],
        mode: TransportMode,
        avoid_tolls: bool = False,
        avoid_highways: bool = False,
    ) -> Tuple[List[Dict[str, Any]], List[str]]:
        """Fetch real road-following routes.

        Returns (routes, data_sources). Driving uses OSRM (alternatives
        supported); cycling/walking use OpenRouteService when a key is set.
        """
        sources: List[str] = []

        if mode == TransportMode.DRIVING:
            data = await self._request_osrm(
                origin,
                destination,
                waypoints,
                avoid_tolls=avoid_tolls,
                avoid_highways=avoid_highways,
            )
            if data:
                sources.append("OSRM")
                routes: List[Dict[str, Any]] = []
                for route_item in data.get("routes", []):
                    coords_list = route_item.get("geometry", {}).get("coordinates", [])
                    path = [Coordinates(lat=c[1], lon=c[0]) for c in coords_list]
                    routes.append({
                        "path": path,
                        "distance_m": route_item.get("distance", 0),
                        "duration_s": route_item.get("duration", 0),
                        "instructions": self._parse_osrm_instructions(route_item),
                    })

                # If OSRM returned fewer than 3 routes, try offset-via routes
                if 0 < len(routes) < 3 and not waypoints:
                    routes = await self._augment_with_via_routes(
                        origin,
                        destination,
                        routes,
                        avoid_tolls=avoid_tolls,
                        avoid_highways=avoid_highways,
                    )
                if routes:
                    return routes, sources

        # Non-driving mode, or OSRM unavailable: try OpenRouteService
        data = await self._request_ors(origin, destination, waypoints, mode)
        if data and data.get("features"):
            sources.append("OpenRouteService")
            feature = data["features"][0]
            coords_list = feature.get("geometry", {}).get("coordinates", [])
            path = [Coordinates(lat=c[1], lon=c[0]) for c in coords_list]
            props = feature.get("properties", {})
            summary = props.get("summary", {})
            return [{
                "path": path,
                "distance_m": summary.get("distance", 0),
                "duration_s": summary.get("duration", 0),
                "instructions": self._parse_ors_instructions(feature),
            }], sources

        return [], sources

    async def _augment_with_via_routes(
        self,
        origin: Coordinates,
        destination: Coordinates,
        routes: List[Dict[str, Any]],
        avoid_tolls: bool = False,
        avoid_highways: bool = False,
    ) -> List[Dict[str, Any]]:
        """Create additional real-road routes via offset intermediate waypoints."""
        if not routes or not routes[0]["path"]:
            return routes
        base_path = routes[0]["path"]
        mid_idx = len(base_path) // 2
        mid_point = base_path[mid_idx]

        offsets = [(0.003, 0.003), (-0.003, -0.003)]
        for off_lat, off_lon in offsets:
            if len(routes) >= 3:
                break
            via = Coordinates(lat=mid_point.lat + off_lat, lon=mid_point.lon + off_lon)
            data = await self._request_osrm(
                origin,
                destination,
                [via],
                avoid_tolls=avoid_tolls,
                avoid_highways=avoid_highways,
            )
            if data and data.get("routes"):
                route_item = data["routes"][0]
                coords_list = route_item.get("geometry", {}).get("coordinates", [])
                routes.append({
                    "path": [Coordinates(lat=c[1], lon=c[0]) for c in coords_list],
                    "distance_m": route_item.get("distance", 0),
                    "duration_s": route_item.get("duration", 0),
                    "instructions": self._parse_osrm_instructions(route_item),
                })
        return routes

    def _generate_route_path(
        self,
        origin: Coordinates,
        destination: Coordinates,
        deviation: float = 0.0,
    ) -> List[Coordinates]:
        """Fallback synthetic path when OSRM is unavailable."""
        num_points = 12
        path = [origin]
        for i in range(1, num_points):
            t = i / num_points
            base_lat = origin.lat + t * (destination.lat - origin.lat)
            base_lon = origin.lon + t * (destination.lon - origin.lon)
            if deviation > 0:
                perp_lat = -(destination.lon - origin.lon)
                perp_lon = destination.lat - origin.lat
                length = math.sqrt(perp_lat**2 + perp_lon**2)
                if length > 0:
                    perp_lat /= length
                    perp_lon /= length
                dev_amount = deviation * math.sin(t * math.pi)
                base_lat += perp_lat * dev_amount
                base_lon += perp_lon * dev_amount
            path.append(
                Coordinates(lat=round(base_lat, 6), lon=round(base_lon, 6))
            )
        path.append(destination)
        return path

    def _calculate_route_distance(self, path: List[Coordinates]) -> float:
        return sum(
            haversine_distance_km(path[i], path[i + 1])
            for i in range(len(path) - 1)
        )

    def _calculate_travel_time(
        self,
        path: List[Coordinates],
        traffic_segments: List[TrafficSegment],
    ) -> float:
        total_time = 0.0
        for segment in traffic_segments:
            distance = haversine_distance_km(
                segment.start_coords, segment.end_coords
            )
            if segment.current_speed > 0:
                total_time += (distance / segment.current_speed) * 60
            else:
                total_time += segment.delay_minutes
        return round(total_time, 1)

    def _calculate_fuel(
        self,
        distance_km: float,
        vehicle_type: str,
        traffic_segments: List[TrafficSegment],
    ) -> Tuple[float, float]:
        base_rate = FUEL_RATES_L_PER_100KM.get(
            vehicle_type, FUEL_RATES_L_PER_100KM["car"]
        )
        traffic_multiplier = 1.0
        for seg in traffic_segments:
            ratio = (
                seg.current_speed / seg.free_flow_speed
                if seg.free_flow_speed > 0
                else 1.0
            )
            if ratio < 0.5:
                traffic_multiplier += 0.12

        liters = (distance_km / 100) * base_rate * traffic_multiplier
        cost = liters * settings.fuel_price_usd_per_liter
        return round(liters, 2), round(cost, 2)

    def _calculate_safety_score(
        self,
        path: List[Coordinates],
        traffic_segments: List[TrafficSegment],
        weather: WeatherCondition,
    ) -> float:
        base_score = 7.5
        base_score -= weather.impact_score * 0.3
        total_incidents = sum(seg.incident_count for seg in traffic_segments)
        base_score -= total_incidents * 0.5
        heavy_segments = sum(
            1
            for seg in traffic_segments
            if seg.congestion_level
            in (TrafficCondition.HEAVY, TrafficCondition.SEVERE)
        )
        base_score -= heavy_segments * 0.3
        return max(0.0, min(10.0, round(base_score, 1)))

    def _calculate_overall_score(
        self,
        metrics: RouteMetrics,
        weights: Dict[str, int],
    ) -> float:
        total_weight = sum(weights.values())
        if total_weight == 0:
            return 50.0

        time_score = max(
            0.0, 100 - (metrics.estimated_time_min / TIME_SCORE_ANCHOR_MIN) * 100
        )
        distance_score = max(
            0.0, 100 - (metrics.distance_km / DISTANCE_SCORE_ANCHOR_KM) * 100
        )
        safety_score = metrics.safety_score * 10
        fuel_score = max(
            0.0, 100 - (metrics.fuel_liters / FUEL_SCORE_ANCHOR_L) * 100
        )
        weather_score = max(0.0, 100 - metrics.weather_impact * 10)

        weighted = (
            time_score * weights.get("time", 85)
            + distance_score * weights.get("distance", 60)
            + safety_score * weights.get("safety", 90)
            + fuel_score * weights.get("fuel", 75)
            + weather_score * WEATHER_WEIGHT_BONUS
        ) / (total_weight + WEATHER_WEIGHT_BONUS)

        return round(weighted, 1)

    def _generate_insights(
        self,
        route: RouteAlternative,
        all_routes: List[RouteAlternative],
    ) -> List[str]:
        insights: List[str] = []
        worst_time = max(r.metrics.estimated_time_min for r in all_routes)
        worst_fuel = max(r.metrics.fuel_liters for r in all_routes)

        time_saved = worst_time - route.metrics.estimated_time_min
        fuel_saved = worst_fuel - route.metrics.fuel_liters

        if time_saved > 3:
            insights.append(
                f"Saves {round(time_saved)} minutes compared to the slowest route."
            )
        if fuel_saved > 0.3:
            insights.append(
                f"More fuel-efficient, saving {round(fuel_saved, 1)} liters."
            )
        if route.metrics.weather_impact < 3:
            insights.append("Weather conditions are favorable along this route.")
        elif route.metrics.weather_impact > 6:
            insights.append("Adverse weather detected — drive with caution.")

        heavy_segments = [
            seg
            for seg in route.traffic_segments
            if seg.congestion_level == TrafficCondition.HEAVY
        ]
        if heavy_segments:
            insights.append(
                f"{len(heavy_segments)} segment(s) with heavy congestion."
            )
        if route.metrics.safety_score >= 8.5:
            insights.append("Excellent safety rating — low incident history.")
        elif route.metrics.safety_score < 6:
            insights.append("Lower safety score — consider alternative at night.")
        return insights

    def _generate_warnings(self, route: RouteAlternative) -> List[str]:
        warnings: List[str] = []
        for seg in route.traffic_segments:
            if seg.incident_count > 0:
                warnings.append(
                    f"Active incident near ({seg.start_coords.lat:.4f}, "
                    f"{seg.start_coords.lon:.4f}) — delay ~{seg.delay_minutes} min."
                )
            if seg.congestion_level == TrafficCondition.SEVERE:
                warnings.append(
                    "Severe congestion detected — consider delaying departure."
                )
        return warnings

    def _worst_traffic(
        self, traffic_segments: List[TrafficSegment]
    ) -> TrafficCondition:
        worst = TrafficCondition.LIGHT
        order = {
            TrafficCondition.LIGHT: 0,
            TrafficCondition.MODERATE: 1,
            TrafficCondition.HEAVY: 2,
            TrafficCondition.SEVERE: 3,
        }
        for seg in traffic_segments:
            if order[seg.congestion_level] > order[worst]:
                worst = seg.congestion_level
        return worst

    async def optimize_routes(
        self,
        origin: Coordinates,
        destination: Coordinates,
        waypoints: Optional[List[Coordinates]] = None,
        time_weight: int = 85,
        distance_weight: int = 60,
        safety_weight: int = 90,
        fuel_weight: int = 75,
        vehicle_type: str = "car",
        transport_mode: TransportMode = TransportMode.DRIVING,
        avoid_tolls: bool = False,
        avoid_highways: bool = False,
    ) -> RouteOptimizationResponse:
        """Production route optimization with real APIs.

        Supports multi-stop trips via ordered waypoints and
        transport-mode-aware routing (driving/cycling/walking).
        """
        start_time = datetime.now(timezone.utc)
        waypoints = waypoints or []

        # Route-level response cache (weights don't change the geometry)
        cache_key = self._route_cache_key(origin, destination, waypoints, transport_mode)
        cached = await cache.get_json(cache_key)
        if cached is not None:
            response = RouteOptimizationResponse(**cached)
            # Keep request_id/timestamp fresh per request
            response.request_id = str(uuid.uuid4())
            response.timestamp = datetime.now(timezone.utc)
            return response

        if isinstance(vehicle_type, VehicleType):
            vehicle_key = vehicle_type.value
        else:
            vehicle_key = str(vehicle_type)

        weather = await self.weather_service.get_weather(origin)
        real_routes, routing_sources = await self._get_real_routes(
            origin,
            destination,
            waypoints,
            transport_mode,
            avoid_tolls=avoid_tolls,
            avoid_highways=avoid_highways,
        )

        route_configs: List[Dict[str, Any]] = [
            {
                "id": "route_a",
                "name": "Route A",
                "description": "Fastest Route",
                "color": "#10b981",
                "deviation": 0.0,
            },
            {
                "id": "route_b",
                "name": "Route B",
                "description": "Balanced Alternative",
                "color": "#f59e0b",
                "deviation": 0.005,
            },
            {
                "id": "route_c",
                "name": "Route C",
                "description": "Scenic Route",
                "color": "#3b82f6",
                "deviation": 0.012,
            },
        ]

        routes: List[RouteAlternative] = []
        for idx, config in enumerate(route_configs):
            instructions: List[NavigationInstruction] = []
            if idx < len(real_routes) and real_routes[idx]:
                real_route = real_routes[idx]
                path = real_route["path"]
                distance_km = real_route["distance_m"] / 1000
                base_time_min = real_route["duration_s"] / 60
                instructions = real_route.get("instructions", [])
            else:
                path = self._generate_route_path(
                    origin, destination, deviation=config["deviation"]
                )
                distance_km = self._calculate_route_distance(path)
                base_time_min = None

            traffic_segments = await self.traffic_service.get_traffic_for_route(
                path
            )

            if base_time_min is None:
                travel_time = self._calculate_travel_time(path, traffic_segments)
            else:
                delay = sum(seg.delay_minutes for seg in traffic_segments)
                travel_time = round(base_time_min + delay, 1)

            fuel_liters, fuel_cost = self._calculate_fuel(
                distance_km, vehicle_key, traffic_segments
            )
            safety = self._calculate_safety_score(path, traffic_segments, weather)
            worst_traffic = self._worst_traffic(traffic_segments)

            metrics = RouteMetrics(
                distance_km=round(distance_km, 1),
                estimated_time_min=round(travel_time, 1),
                fuel_liters=fuel_liters,
                fuel_cost_usd=fuel_cost,
                safety_score=safety,
                traffic_condition=worst_traffic,
                weather_impact=weather.impact_score,
                overall_score=0,
                co2_emissions_kg=round(
                    fuel_liters * settings.co2_kg_per_liter, 2
                ),
            )

            route = RouteAlternative(
                route_id=config["id"],
                name=config["name"],
                description=config["description"],
                color=config["color"],
                path=path,
                metrics=metrics,
                traffic_segments=traffic_segments,
                instructions=instructions,
                warnings=[],
                insights=[],
            )
            routes.append(route)

        weights = {
            "time": time_weight,
            "distance": distance_weight,
            "safety": safety_weight,
            "fuel": fuel_weight,
        }
        for route in routes:
            route.metrics.overall_score = self._calculate_overall_score(
                route.metrics, weights
            )

        routes.sort(key=lambda r: r.metrics.overall_score, reverse=True)
        routes[0].is_recommended = True

        for route in routes:
            route.insights = self._generate_insights(route, routes)
            route.warnings = self._generate_warnings(route)

        worst_route = min(routes, key=lambda r: r.metrics.overall_score)
        time_saved = (
            worst_route.metrics.estimated_time_min
            - routes[0].metrics.estimated_time_min
        )
        fuel_saved = (
            worst_route.metrics.fuel_cost_usd - routes[0].metrics.fuel_cost_usd
        )

        data_sources = ["OpenWeatherMap", "OpenStreetMap/Nominatim", *routing_sources]
        processing_time = int(
            (datetime.now(timezone.utc) - start_time).total_seconds() * 1000
        )

        response = RouteOptimizationResponse(
            request_id=str(uuid.uuid4()),
            timestamp=datetime.now(timezone.utc),
            origin_address=None,
            destination_address=None,
            weather=weather,
            routes=routes,
            recommended_route_id=routes[0].route_id,
            time_saved_vs_worst_min=round(max(0.0, time_saved), 1),
            fuel_saved_vs_worst_usd=round(max(0.0, fuel_saved), 2),
            processing_time_ms=processing_time,
            data_sources=data_sources,
        )

        # Cache the full response for identical future requests
        await cache.set_json(
            cache_key, response.model_dump(mode="json"), settings.route_cache_ttl
        )
        return response

    async def close(self) -> None:
        await self.weather_service.close()
        await self.traffic_service.close()
        if self._owns_routing_client:
            await self.routing_client.aclose()