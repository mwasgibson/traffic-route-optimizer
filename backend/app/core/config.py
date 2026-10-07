"""Application configuration using Pydantic Settings."""
import json
from typing import List, Union
from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Production settings loaded from environment variables."""

    app_name: str = "Traffic Route Optimizer"
    debug: bool = False
    cors_origins: Union[List[str], str] = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ]

    # === REAL API KEYS (required for production) ===
    # Get free key at: https://openweathermap.org/api
    openweather_api_key: str = ""

    # Get free key at: https://developer.tomtom.com
    tomtom_api_key: str = ""

    # Get free key at: https://openrouteservice.org/dev/#/login
    openroute_api_key: str = ""

    google_maps_api_key: str = ""

    # Redis (optional caching layer)
    redis_url: str = "redis://localhost:6379/0"
    # Fail fast to in-memory cache instead of retrying Redis forever
    redis_max_connections: int = 10

    # Cache TTL (seconds)
    weather_cache_ttl: int = 600      # 10 minutes
    traffic_cache_ttl: int = 120      # 2 minutes
    route_cache_ttl: int = 300        # 5 minutes
    geocode_cache_ttl: int = 86400    # 24 hours

    # === Rate limiting (requests per window, per client IP) ===
    rate_limit_requests: int = 60
    rate_limit_window_seconds: int = 60

    # === External API behavior ===
    http_timeout_seconds: float = 15.0
    max_search_query_length: int = 200
    max_waypoints: int = 8

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"  # Prevents crashes if unhandled vars exist in .env
    )

    @field_validator("cors_origins", mode="before")
    @classmethod
    def assemble_cors_origins(cls, v: Union[str, List[str]]) -> List[str]:
        """Allow comma-separated strings or list inputs for CORS origins."""
        if isinstance(v, str):
            if v.startswith("["):
                parsed = json.loads(v)
                return [str(origin) for origin in parsed]
            return [i.strip() for i in v.split(",") if i.strip()]
        return v


settings = Settings()