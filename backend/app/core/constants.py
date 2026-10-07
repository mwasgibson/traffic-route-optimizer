"""Shared constants for routing, fuel, and scoring.

Keeps magic numbers out of service methods and gives a single place to tune.
"""

from typing import Dict

# Fuel consumption rates (L/100km) by vehicle type
FUEL_RATES_L_PER_100KM: Dict[str, float] = {
    "car": 6.5,
    "motorcycle": 3.5,
    "truck": 25.0,
    "bus": 35.0,
}

DEFAULT_VEHICLE = "car"

# Overall-score normalization anchors (used in weighted scoring)
TIME_SCORE_ANCHOR_MIN = 120.0  # minutes → score approaches 0
DISTANCE_SCORE_ANCHOR_KM = 50.0
FUEL_SCORE_ANCHOR_L = 5.0
WEATHER_WEIGHT_BONUS = 50  # implicit weight for weather in overall score

# Traffic sampling: max TomTom calls per route path (avoid N+1 blowups)
MAX_TRAFFIC_SAMPLES_PER_ROUTE = 12

# OSRM public instance (demo). Prefer self-hosted or OpenRouteService in production.
OSRM_DRIVING_URL = "http://router.project-osrm.org/route/v1/driving"

NOMINATIM_BASE_URL = "https://nominatim.openstreetmap.org"
NOMINATIM_USER_AGENT = (
    "TrafficRouteOptimizerApp/1.0 (contact: admin@trafficoptimizer.local)"
)