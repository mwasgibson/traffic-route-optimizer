"""Tests for route optimization API."""
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.main import app


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