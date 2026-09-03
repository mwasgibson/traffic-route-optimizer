"""Production route optimization engine with real routing APIs."""
import math
from typing import List, Dict, Tuple, Any
from datetime import datetime, timezone
import uuid
import httpx

from ..models.schemas import (
    Coordinates, RouteAlternative, RouteMetrics, RouteOptimizationResponse,
    TrafficCondition, WeatherCondition, TrafficSegment
)
from ..core.config import settings
from .weather_service import WeatherService
from .traffic_service import TrafficService


class RouteOptimizer:
    """Production multi-factor route optimization engine."""

    OSRM_URL = "http://router.project-osrm.org/route/v1/driving"

    # Fuel consumption rates (L/100km) by vehicle type
    FUEL_RATES = {
        "car": 6.5,
        "motorcycle": 3.5,
        "truck": 25.0,
        "bus": 35.0
    }

    CO2_PER_LITER = 2.31

    def __init__(self):
        self.weather_service = WeatherService()
        self.traffic_service = TrafficService()
        self.routing_client = httpx.AsyncClient(timeout=30.0)

    def _haversine_distance(self, p1: Coordinates, p2: Coordinates) -> float:
        R = 6371
        lat1, lon1 = math.radians(p1.lat), math.radians(p1.lon)
        lat2, lon2 = math.radians(p2.lat), math.radians(p2.lon)
        dlat = lat2 - lat1
        dlon = lon2 - lon1
        a = math.sin(dlat/2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon/2)**2
        return R * 2 * math.asin(math.sqrt(a))

    async def _get_real_routes_from_osrm(
        self,
        origin: Coordinates,
        destination: Coordinates
    ) -> List[Dict[str, Any]]:
        """Fetch real road-following routes using the free OSRM engine."""
        try:
            coords = f"{origin.lon},{origin.lat};{destination.lon},{destination.lat}"
            url = f"{self.OSRM_URL}/{coords}"

            # OSRM expects alternatives=3 or number/boolean
            params: Dict[str, Any] = {
                    "overview": "full",
                    "geometries": "geojson",
                    "steps": "true",
                    "alternatives": "3"
                }

            response = await self.routing_client.get(url, params=params, timeout=15.0)
            if response.status_code != 200:
                return []

            data = response.json()
            routes: List[Dict[str, Any]] = []

            for route_item in data.get("routes", []):
                geometry = route_item.get("geometry", {})
                coords_list = geometry.get("coordinates", [])

                # OSRM returns [lon, lat], convert to Coordinates(lat, lon)
                path = [Coordinates(lat=c[1], lon=c[0]) for c in coords_list]

                routes.append({
                    "path": path,
                    "distance_m": route_item.get("distance", 0),
                    "duration_s": route_item.get("duration", 0)
                })

            # If OSRM returned fewer than 3 routes, create additional real-road routes 
            # by inserting offset waypoints along the road network:
            if len(routes) < 3 and len(routes) > 0:
                base_path = routes[0]["path"]
                mid_idx = len(base_path) // 2
                mid_point = base_path[mid_idx]

                # Generate up to 3 routes using intermediate road waypoints
                offsets = [(0.003, 0.003), (-0.003, -0.003)]
                for off_lat, off_lon in offsets:
                    if len(routes) >= 3:
                        break
                    via_lat = mid_point.lat + off_lat
                    via_lon = mid_point.lon + off_lon
                    
                    via_coords = f"{origin.lon},{origin.lat};{via_lon},{via_lat};{destination.lon},{destination.lat}"
                    via_url = f"{self.OSRM_URL}/{via_coords}"
                    via_res = await self.routing_client.get(
                        via_url, 
                        params={"overview": "full", "geometries": "geojson"}, 
                        timeout=10.0
                    )
                    if via_res.status_code == 200:
                        vdata = via_res.json()
                        if vdata.get("routes"):
                            vroute = vdata["routes"][0]
                            vcoords = vroute.get("geometry", {}).get("coordinates", [])
                            routes.append({
                                "path": [Coordinates(lat=c[1], lon=c[0]) for c in vcoords],
                                "distance_m": vroute.get("distance", 0),
                                "duration_s": vroute.get("duration", 0)
                            })

            return routes

        except Exception:
            return []

    def _generate_route_path(
        self,
        origin: Coordinates,
        destination: Coordinates,
        deviation: float = 0.0
    ) -> List[Coordinates]:
        """Fallback synthetic route path generator."""
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

            path.append(Coordinates(lat=round(base_lat, 6), lon=round(base_lon, 6)))

        path.append(destination)
        return path

    def _calculate_route_distance(self, path: List[Coordinates]) -> float:
        return sum(
            self._haversine_distance(path[i], path[i+1])
            for i in range(len(path) - 1)
        )

    def _calculate_travel_time(
        self,
        path: List[Coordinates],
        traffic_segments: List[TrafficSegment]
    ) -> float:
        total_time = 0.0
        for segment in traffic_segments:
            distance = self._haversine_distance(segment.start_coords, segment.end_coords)
            if segment.current_speed > 0:
                total_time += (distance / segment.current_speed) * 60
            else:
                total_time += segment.delay_minutes
        return round(total_time, 1)

    def _calculate_fuel(
        self,
        distance_km: float,
        vehicle_type: str,
        traffic_segments: List[TrafficSegment]
    ) -> Tuple[float, float]:
        base_rate = self.FUEL_RATES.get(vehicle_type, 6.5)
        traffic_multiplier = 1.0
        for seg in traffic_segments:
            ratio = seg.current_speed / seg.free_flow_speed if seg.free_flow_speed > 0 else 1.0
            if ratio < 0.5:
                traffic_multiplier += 0.12

        liters = (distance_km / 100) * base_rate * traffic_multiplier
        cost = liters * 1.50
        return round(liters, 2), round(cost, 2)

    def _calculate_safety_score(
        self,
        path: List[Coordinates],
        traffic_segments: List[TrafficSegment],
        weather: WeatherCondition
    ) -> float:
        base_score = 7.5
        base_score -= weather.impact_score * 0.3
        total_incidents = sum(seg.incident_count for seg in traffic_segments)
        base_score -= total_incidents * 0.5
        heavy_segments = sum(
            1 for seg in traffic_segments
            if seg.congestion_level in [TrafficCondition.HEAVY, TrafficCondition.SEVERE]
        )
        base_score -= heavy_segments * 0.3
        return max(0, min(10, round(base_score, 1)))

    def _calculate_overall_score(
        self,
        metrics: RouteMetrics,
        weights: Dict[str, int]
    ) -> float:
        total_weight = sum(weights.values())
        if total_weight == 0:
            return 50.0

        time_score = max(0, 100 - (metrics.estimated_time_min / 120) * 100)
        distance_score = max(0, 100 - (metrics.distance_km / 50) * 100)
        safety_score = metrics.safety_score * 10
        fuel_score = max(0, 100 - (metrics.fuel_liters / 5) * 100)
        weather_score = max(0, 100 - metrics.weather_impact * 10)

        weighted = (
            time_score * weights.get("time", 85) +
            distance_score * weights.get("distance", 60) +
            safety_score * weights.get("safety", 90) +
            fuel_score * weights.get("fuel", 75) +
            weather_score * 50
        ) / (total_weight + 50)

        return round(weighted, 1)

    def _generate_insights(
        self,
        route: RouteAlternative,
        all_routes: List[RouteAlternative]
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
            seg for seg in route.traffic_segments
            if seg.congestion_level == TrafficCondition.HEAVY
        ]
        if heavy_segments:
            insights.append(f"{len(heavy_segments)} segment(s) with heavy congestion.")

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
                    f"Active incident near ({seg.start_coords.lat:.4f}, {seg.start_coords.lon:.4f}) — "
                    f"delay ~{seg.delay_minutes} min."
                )
            if seg.congestion_level == TrafficCondition.SEVERE:
                warnings.append("Severe congestion detected — consider delaying departure.")
        return warnings

    async def optimize_routes(
        self,
        origin: Coordinates,
        destination: Coordinates,
        time_weight: int = 85,
        distance_weight: int = 60,
        safety_weight: int = 90,
        fuel_weight: int = 75,
        vehicle_type: str = "car",
        avoid_tolls: bool = False,
        avoid_highways: bool = False
    ) -> RouteOptimizationResponse:
        """Production route optimization with real APIs."""
        start_time = datetime.now(timezone.utc)

        # Fetch real weather data
        weather = await self.weather_service.get_weather(origin)

        # Fetch real road paths from OSRM
        osrm_routes = await self._get_real_routes_from_osrm(origin, destination)

        route_configs: List[Dict[str, Any]] = [
            {"id": "route_a", "name": "Route A", "description": "Fastest Route", "color": "#10b981", "deviation": 0.0},
            {"id": "route_b", "name": "Route B", "description": "Balanced Alternative", "color": "#f59e0b", "deviation": 0.005},
            {"id": "route_c", "name": "Route C", "description": "Scenic Route", "color": "#3b82f6", "deviation": 0.012},
        ]

        routes: List[RouteAlternative] = []
        for idx, config in enumerate(route_configs):
            if idx < len(osrm_routes) and osrm_routes[idx]:
                real_route = osrm_routes[idx]
                path = real_route["path"]
                distance_km = real_route["distance_m"] / 1000
                base_time_min = real_route["duration_s"] / 60
            else:
                path = self._generate_route_path(origin, destination, deviation=config["deviation"])
                distance_km = self._calculate_route_distance(path)
                base_time_min = None

            traffic_segments = await self.traffic_service.get_traffic_for_route(path)

            if base_time_min is None:
                travel_time = self._calculate_travel_time(path, traffic_segments)
            else:
                delay = sum(seg.delay_minutes for seg in traffic_segments)
                travel_time = round(base_time_min + delay, 1)

            fuel_liters, fuel_cost = self._calculate_fuel(distance_km, vehicle_type, traffic_segments)
            safety = self._calculate_safety_score(path, traffic_segments, weather)

            worst_traffic = TrafficCondition.LIGHT
            for seg in traffic_segments:
                if seg.congestion_level.value == "severe":
                    worst_traffic = TrafficCondition.SEVERE
                    break
                elif seg.congestion_level.value == "heavy":
                    worst_traffic = TrafficCondition.HEAVY
                elif seg.congestion_level.value == "moderate" and worst_traffic == TrafficCondition.LIGHT:
                    worst_traffic = TrafficCondition.MODERATE

            metrics = RouteMetrics(
                distance_km=round(distance_km, 1),
                estimated_time_min=round(travel_time, 1),
                fuel_liters=fuel_liters,
                fuel_cost_usd=fuel_cost,
                safety_score=safety,
                traffic_condition=worst_traffic,
                weather_impact=weather.impact_score,
                overall_score=0,
                co2_emissions_kg=round(fuel_liters * self.CO2_PER_LITER, 2)
            )

            route = RouteAlternative(
                route_id=config["id"],
                name=config["name"],
                description=config["description"],
                color=config["color"],
                path=path,
                metrics=metrics,
                traffic_segments=traffic_segments,
                warnings=[],
                insights=[]
            )

            routes.append(route)

        weights = {"time": time_weight, "distance": distance_weight, "safety": safety_weight, "fuel": fuel_weight}
        for route in routes:
            route.metrics.overall_score = self._calculate_overall_score(route.metrics, weights)

        routes.sort(key=lambda r: r.metrics.overall_score, reverse=True)
        routes[0].is_recommended = True

        for route in routes:
            route.insights = self._generate_insights(route, routes)
            route.warnings = self._generate_warnings(route)

        worst_route = min(routes, key=lambda r: r.metrics.overall_score)
        time_saved = worst_route.metrics.estimated_time_min - routes[0].metrics.estimated_time_min
        fuel_saved = worst_route.metrics.fuel_cost_usd - routes[0].metrics.fuel_cost_usd

        processing_time = int((datetime.now(timezone.utc) - start_time).total_seconds() * 1000)

        data_sources = ["OpenWeatherMap", "OpenStreetMap/Nominatim", "OSRM"]

        return RouteOptimizationResponse(
            request_id=str(uuid.uuid4()),
            timestamp=datetime.now(timezone.utc),
            origin_address=None,
            destination_address=None,
            weather=weather,
            routes=routes,
            recommended_route_id=routes[0].route_id,
            time_saved_vs_worst_min=round(max(0, time_saved), 1),
            fuel_saved_vs_worst_usd=round(max(0, fuel_saved), 2),
            processing_time_ms=processing_time,
            data_sources=data_sources
        )

    async def close(self):
        await self.weather_service.close()
        await self.traffic_service.close()
        await self.routing_client.aclose()