"""Application configuration using Pydantic Settings."""
import json
from typing import List, Union

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Production settings loaded from environment variables."""

    app_name: str = "Traffic Route Optimizer"
    debug: bool = False
    # Comma-separated string is the canonical env form; list is accepted too.
    cors_origins: Union[List[str], str] = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ]

    # === API keys (free tiers sufficient for development) ===
    # https://openweathermap.org/api
    openweather_api_key: str = ""
    # https://developer.tomtom.com
    tomtom_api_key: str = ""
    # https://openrouteservice.org/dev/#/login (reserved for future ORS routing)
    openroute_api_key: str = ""
    google_maps_api_key: str = ""

    # Redis (optional caching layer)
    redis_url: str = "redis://localhost:6379/0"

    # Cache TTL (seconds)
    weather_cache_ttl: int = 600  # 10 minutes
    traffic_cache_ttl: int = 120  # 2 minutes
    route_cache_ttl: int = 300  # 5 minutes
    geocode_cache_ttl: int = 86400  # 24 hours

    # Economics / scoring defaults (override via env if needed)
    fuel_price_usd_per_liter: float = 1.50
    co2_kg_per_liter: float = 2.31

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
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

    @property
    def cors_origins_list(self) -> List[str]:
        """Always return a list of origins."""
        if isinstance(self.cors_origins, list):
            return self.cors_origins
        return self.assemble_cors_origins(self.cors_origins)


settings = Settings()
