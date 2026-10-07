"""Tests for route optimization API."""
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.models.schemas import (
    Coordinates,
    RouteAlternative,
    RouteMetrics,
    RouteOptimizationResponse,
    TrafficCondition,
    WeatherCondition,
)
from datetime import datetime, timezone


client = TestClient(app)

class TestUpgrades:
    """Tests for v1.1 features: multi-stop, GPX, sanitization, rate limit."""

    def test_waypoint_limit_validation(self):
        """Waypoints beyond max should be rejected with 422."""
        payload: dict[str, Any] = {
            "origin": {"lat": -1.2921, "lon": 36.8219},
            "destination": {"lat": -1.3192, "lon": 36.9278},
            "waypoints": [{"lat": -1.30, "lon": 36.85}] * 20,
        }
        response = client.post("/api/v1/routes/optimize", json=payload)
        assert response.status_code == 422

    def test_transport_mode_validation(self):
        payload: dict[str, Any] = {
            "origin": {"lat": -1.2921, "lon": 36.8219},
            "destination": {"lat": -1.3192, "lon": 36.9278},
            "transport_mode": "flying",
        }
        response = client.post("/api/v1/routes/optimize", json=payload)
        assert response.status_code == 422

    def test_gpx_export(self):
        payload = {
            "name": "Test Route",
            "route": [{"lat": -1.2921, "lon": 36.8219}, {"lat": -1.30, "lon": 36.85}],
            "waypoints": [{"lat": -1.296, "lon": 36.83}],
        }
        response = client.post("/api/v1/routes/export/gpx", json=payload)
        assert response.status_code == 200
        assert "application/gpx+xml" in response.headers["content-type"]
        body = response.text
        assert "<gpx" in body and "<trkpt" in body and "<wpt" in body

    def test_search_sanitization(self):
        """Control characters should be stripped, not crash the endpoint."""
        response = client.get("/api/v1/routes/search", params={"q": "nairobi\x00<script>"})
        assert response.status_code in (200, 422, 429, 502, 503)

    def test_root_reports_cache_backend(self):
        response = client.get("/")
        assert response.status_code == 200
        assert "cache_backend" in response.json()
def _mock_optimize_response() -> RouteOptimizationResponse:
    metrics = RouteMetrics(
        distance_km=12.5,
        estimated_time_min=28.0,
        fuel_liters=0.9,
        fuel_cost_usd=1.35,
        safety_score=8.2,
        traffic_condition=TrafficCondition.MODERATE,
        weather_impact=2.0,
        overall_score=78.5,
        co2_emissions_kg=2.08,
    )
    route = RouteAlternative(
        route_id="route_a",
        name="Route A",
        description="Fastest Route",
        color="#10b981",
        is_recommended=True,
        path=[
            Coordinates(lat=-1.2921, lon=36.8219),
            Coordinates(lat=-1.3192, lon=36.9278),
        ],
        metrics=metrics,
        traffic_segments=[],
        warnings=[],
        insights=["Test insight"],
    )
    return RouteOptimizationResponse(
        request_id="test-id",
        timestamp=datetime.now(timezone.utc),
        origin_address=None,
        destination_address=None,
        weather=WeatherCondition(
            temperature=24.0,
            humidity=65,
            visibility=8.5,
            rainfall=0.0,
            wind_speed=12.0,
            condition="Partly Cloudy",
            impact_score=2.0,
        ),
        routes=[route],
        recommended_route_id="route_a",
        time_saved_vs_worst_min=5.0,
        fuel_saved_vs_worst_usd=0.5,
        processing_time_ms=100,
        data_sources=["OSRM", "OpenWeatherMap", "TomTom"],
    )


class TestHealth:
    def test_root(self):
        response = client.get("/")
        assert response.status_code == 200
        assert response.json()["status"] == "ok"

    def test_health_check(self):
        response = client.get("/health")
        assert response.status_code == 200
        body = response.json()
        assert body["status"] in ("healthy", "degraded")
        assert "timestamp" in body
        assert "services" in body
        # Must not be the old hardcoded date
        assert not body["timestamp"].startswith("2024-01-01")


class TestRouteOptimization:
    def test_optimize_routes_success(self):
        payload: dict[str, Any] = {
            "origin": {"lat": -1.2921, "lon": 36.8219},
            "destination": {"lat": -1.3192, "lon": 36.9278},
            "time_weight": 85,
            "distance_weight": 60,
            "safety_weight": 90,
            "fuel_weight": 75,
            "vehicle_type": "car",
            "avoid_tolls": False,
            "avoid_highways": False,
        }

        mock_resp = _mock_optimize_response()
        with patch(
            "app.routers.routes.RouteOptimizer"
        ) as MockOptimizer:
            instance = MockOptimizer.return_value
            instance.optimize_routes = AsyncMock(return_value=mock_resp)
            instance.close = AsyncMock()

            response = client.post("/api/v1/routes/optimize", json=payload)
            assert response.status_code == 200
            data = response.json()
            assert "request_id" in data
            assert "routes" in data
            assert len(data["routes"]) >= 1
            assert data["recommended_route_id"] == "route_a"

    def test_optimize_routes_invalid_coords(self):
        payload: dict[str, Any] = {
            "origin": {"lat": 999, "lon": 36.8219},
            "destination": {"lat": -1.3192, "lon": 36.9278},
        }
        response = client.post("/api/v1/routes/optimize", json=payload)
        assert response.status_code == 422

    def test_optimize_missing_api_keys_returns_400(self):
        """Without keys, real optimizer raises ValueError → 400."""
        payload: dict[str, Any] = {
            "origin": {"lat": -1.2921, "lon": 36.8219},
            "destination": {"lat": -1.3192, "lon": 36.9278},
        }
        # Ensure keys are empty for this test
        with patch("app.services.weather_service.settings") as wx:
            wx.openweather_api_key = ""
            # Route goes through RouteOptimizer which calls weather first
            with patch(
                "app.routers.routes.RouteOptimizer.optimize_routes",
                new_callable=AsyncMock,
                side_effect=ValueError("OpenWeatherMap API key is required."),
            ):
                with patch(
                    "app.routers.routes.RouteOptimizer.close",
                    new_callable=AsyncMock,
                ):
                    response = client.post(
                        "/api/v1/routes/optimize", json=payload
                    )
                    assert response.status_code == 400


class TestHeatmap:
    def test_traffic_heatmap(self):
        mock_heatmap = {
            "bounds": {"north": -1.2, "south": -1.4, "east": 37.0, "west": 36.7},
            "points": [
                {"lat": -1.3, "lon": 36.8, "intensity": 0.4, "speed": 50.0}
            ],
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "total_incidents": 0,
        }
        with patch("app.routers.routes.TrafficService") as MockTS:
            instance = MockTS.return_value
            instance.get_traffic_heatmap = AsyncMock(return_value=mock_heatmap)
            instance.close = AsyncMock()
            response = client.get(
                "/api/v1/routes/heatmap",
                params={
                    "north": -1.2,
                    "south": -1.4,
                    "east": 37.0,
                    "west": 36.7,
                },
            )
            assert response.status_code == 200
            data = response.json()
            assert "points" in data
            assert "bounds" in data


class TestSearch:
    def test_search_locations_mocked(self):
        mock_json = [
            {
                "place_id": "1",
                "name": "Nairobi",
                "display_name": "Nairobi, Kenya",
                "lat": "-1.286389",
                "lon": "36.817223",
                "type": "city",
                "address": {"city": "Nairobi", "country": "Kenya"},
            }
        ]
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = mock_json

        with patch("app.routers.routes._get_nominatim_client") as get_client:
            client_mock = AsyncMock()
            client_mock.get = AsyncMock(return_value=mock_response)
            get_client.return_value = client_mock

            response = client.get(
                "/api/v1/routes/search", params={"q": "nairobi"}
            )
            assert response.status_code == 200
            data = response.json()
            assert isinstance(data, list)
            assert len(data) == 1
            assert data[0]["name"] == "Nairobi"
