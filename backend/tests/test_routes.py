"""Tests for route optimization API."""
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


class TestRouteOptimization:
    """Test suite for route optimization endpoints."""

    def test_health_check(self):
        """Test health endpoint."""
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json()["status"] == "healthy"

    def test_optimize_routes_success(self):
        """Test successful route optimization."""
        payload: dict[str, Any] = {
            "origin": {"lat": -1.2921, "lon": 36.8219},
            "destination": {"lat": -1.3192, "lon": 36.9278},
            "time_weight": 85,
            "distance_weight": 60,
            "safety_weight": 90,
            "fuel_weight": 75,
            "vehicle_type": "car",
            "avoid_tolls": False,
            "avoid_highways": False
        }

        response = client.post("/api/v1/routes/optimize", json=payload)
        assert response.status_code == 200

        data = response.json()
        assert "request_id" in data
        assert "routes" in data
        assert len(data["routes"]) >= 2
        assert "recommended_route_id" in data
        assert "weather" in data

        # Check first route has required fields
        route = data["routes"][0]
        assert "route_id" in route
        assert "metrics" in route
        assert "path" in route
        assert route["metrics"]["overall_score"] > 0

    def test_optimize_routes_invalid_coords(self):
        """Test with invalid coordinates."""
        payload: dict[str, Any] = {
            "origin": {"lat": 999, "lon": 36.8219},
            "destination": {"lat": -1.3192, "lon": 36.9278}
        }

        response = client.post("/api/v1/routes/optimize", json=payload)
        assert response.status_code == 422

    def test_traffic_heatmap(self):
        """Test traffic heatmap endpoint."""
        response = client.get(
            "/api/v1/routes/heatmap",
            params={"north": -1.2, "south": -1.4, "east": 37.0, "west": 36.7}
        )
        assert response.status_code == 200

        data = response.json()
        assert "points" in data
        assert "bounds" in data
        assert len(data["points"]) > 0

    def test_search_locations(self):
        """Test location search."""
        response = client.get("/api/v1/routes/search", params={"q": "nairobi"})
        assert response.status_code == 200
        assert isinstance(response.json(), list)