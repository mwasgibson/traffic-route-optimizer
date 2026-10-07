"""Pydantic models for request/response validation."""
from pydantic import BaseModel, Field, field_validator
from typing import List, Optional, Dict, Any
from enum import Enum
from datetime import datetime

from ..core.config import settings


class TransportMode(str, Enum):
    """Supported routing profiles."""
    DRIVING = "driving"
    CYCLING = "cycling"
    WALKING = "walking"


class Coordinates(BaseModel):
    """Geographic coordinates."""
    lat: float = Field(..., ge=-90, le=90, description="Latitude")
    lon: float = Field(..., ge=-180, le=180, description="Longitude")


class NavigationInstruction(BaseModel):
    """A single turn-by-turn navigation step."""
    instruction: str = Field(..., description="Human-readable instruction")
    distance_m: float = Field(..., description="Distance covered by this step")
    duration_s: float = Field(..., description="Duration of this step")
    maneuver_type: str = Field(..., description="Maneuver type (turn, merge, arrive...)")
    street_name: Optional[str] = Field(None, description="Street/road name if known")


class RouteRequest(BaseModel):
    """Request model for route optimization."""
    origin: Coordinates
    destination: Coordinates

    # Multi-stop: optional intermediate stops visited in order
    waypoints: List[Coordinates] = Field(
        default_factory=list,
        description="Optional intermediate stops, visited in order",
    )

    # Optimization preferences (0-100)
    time_weight: int = Field(85, ge=0, le=100, description="Weight for travel time")
    distance_weight: int = Field(60, ge=0, le=100, description="Weight for distance")
    safety_weight: int = Field(90, ge=0, le=100, description="Weight for safety")
    fuel_weight: int = Field(75, ge=0, le=100, description="Weight for fuel efficiency")

    # Vehicle type affects fuel calculation
    vehicle_type: str = Field("car", description="car, motorcycle, truck, bus")

    # Routing profile
    transport_mode: TransportMode = Field(
        TransportMode.DRIVING,
        description="Routing profile: driving, cycling, walking",
    )

    # Avoid options
    avoid_tolls: bool = False
    avoid_highways: bool = False

    @field_validator("waypoints")
    @classmethod
    def limit_waypoints(cls, v: List[Coordinates]) -> List[Coordinates]:
        if len(v) > settings.max_waypoints:
            raise ValueError(
                f"Too many waypoints: {len(v)} (max {settings.max_waypoints})"
            )
        return v

    class Config:
        json_schema_extra: Dict[str, Any] = {
            "example": {
                "origin": {"lat": -1.2921, "lon": 36.8219},
                "destination": {"lat": -1.3192, "lon": 36.9278},
                "waypoints": [{"lat": -1.3032, "lon": 36.8582}],
                "time_weight": 85,
                "distance_weight": 60,
                "safety_weight": 90,
                "fuel_weight": 75,
                "vehicle_type": "car",
                "transport_mode": "driving",
                "avoid_tolls": False,
                "avoid_highways": False
            }
        }


class TrafficCondition(str, Enum):
    """Traffic condition levels."""
    LIGHT = "light"
    MODERATE = "moderate"
    HEAVY = "heavy"
    SEVERE = "severe"


class WeatherCondition(BaseModel):
    """Current weather conditions."""
    temperature: float = Field(..., description="Temperature in Celsius")
    humidity: int = Field(..., ge=0, le=100, description="Humidity percentage")
    visibility: float = Field(..., description="Visibility in km")
    rainfall: float = Field(0, description="Rainfall in mm")
    wind_speed: float = Field(..., description="Wind speed in km/h")
    condition: str = Field(..., description="Weather condition description")
    impact_score: float = Field(..., ge=0, le=10, description="Impact on driving (0-10)")

    class Config:
        json_schema_extra: Dict[str, Any] = {
            "example": {
                "temperature": 24.0,
                "humidity": 65,
                "visibility": 8.5,
                "rainfall": 0.0,
                "wind_speed": 12.0,
                "condition": "Partly cloudy",
                "impact_score": 2.1
            }
        }


class TrafficSegment(BaseModel):
    """Traffic data for a road segment."""
    segment_id: str
    start_coords: Coordinates
    end_coords: Coordinates
    current_speed: float = Field(..., description="Current speed in km/h")
    free_flow_speed: float = Field(..., description="Free flow speed in km/h")
    congestion_level: TrafficCondition
    delay_minutes: float = Field(0, description="Estimated delay in minutes")
    incident_count: int = Field(0, description="Number of active incidents")


class RouteMetrics(BaseModel):
    """Metrics for a single route."""
    distance_km: float
    estimated_time_min: float
    fuel_liters: float
    fuel_cost_usd: float
    safety_score: float = Field(..., ge=0, le=10)
    traffic_condition: TrafficCondition
    weather_impact: float = Field(..., ge=0, le=10)
    overall_score: float = Field(..., ge=0, le=100)
    co2_emissions_kg: float


class RouteAlternative(BaseModel):
    """A single route alternative."""
    route_id: str
    name: str
    description: str
    color: str = Field(..., description="Hex color for visualization")
    is_recommended: bool = False

    # Path as list of coordinates
    path: List[Coordinates]

    # Detailed metrics
    metrics: RouteMetrics

    # Traffic segments along route
    traffic_segments: List[TrafficSegment] = []

    # Turn-by-turn navigation instructions
    instructions: List[NavigationInstruction] = []

    # Warnings
    warnings: List[str] = []

    # AI insights
    insights: List[str] = []


class RouteOptimizationResponse(BaseModel):
    """Response model for route optimization."""
    request_id: str
    timestamp: datetime
    origin_address: Optional[str] = None
    destination_address: Optional[str] = None

    # Current conditions
    weather: WeatherCondition

    # Route alternatives
    routes: List[RouteAlternative]

    # Summary
    recommended_route_id: str
    time_saved_vs_worst_min: float
    fuel_saved_vs_worst_usd: float

    # Metadata
    processing_time_ms: int
    data_sources: List[str]


class TrafficHeatmapPoint(BaseModel):
    """Point for traffic heatmap."""
    lat: float
    lon: float
    intensity: float = Field(..., ge=0, le=1, description="Congestion intensity 0-1")
    speed: float


class TrafficHeatmapResponse(BaseModel):
    """Traffic heatmap data."""
    bounds: Dict[str, float]  # north, south, east, west
    points: List[TrafficHeatmapPoint]
    timestamp: datetime
    total_incidents: int


class LocationSearchResult(BaseModel):
    """Geocoding search result."""
    place_id: str
    name: str
    address: str
    coordinates: Coordinates
    type: str


class ErrorResponse(BaseModel):
    """Standard error response."""
    error: str
    detail: Optional[str] = None
    code: Optional[str] = None


class GpxExportRequest(BaseModel):
    """Request model for GPX export."""
    name: str = Field("Traffic Route Optimizer Export", max_length=120)
    route: List[Coordinates] = Field(..., min_length=2)
    waypoints: List[Coordinates] = Field(default_factory=list)