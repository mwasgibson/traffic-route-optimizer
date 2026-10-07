"""Production weather data service using OpenWeatherMap API."""
import logging
from typing import Any, Dict

import httpx
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
)

from ..models.schemas import WeatherCondition, Coordinates
from ..core.config import settings
from .cache import cache

logger = logging.getLogger(__name__)


class WeatherService:
    """Production weather service using OpenWeatherMap API."""

    BASE_URL = "https://api.openweathermap.org/data/2.5"

    def __init__(self) -> None:
        self.api_key = settings.openweather_api_key
        self.client = httpx.AsyncClient(
            timeout=settings.http_timeout_seconds,
            headers={"User-Agent": "TrafficRouteOptimizer/1.1"},
        )

    def _get_cache_key(self, lat: float, lon: float) -> str:
        return f"weather:{round(lat, 2)}:{round(lon, 2)}"

    def _calculate_impact_score(self, data: Dict[str, Any]) -> float:
        """Calculate weather impact score (0-10, higher = worse for driving)."""
        score = 0.0

        # Rain impact
        rain_mm = data.get("rain", {}).get("1h", 0)
        if rain_mm > 0:
            score += min(rain_mm * 2, 5)

        # Snow impact (worse than rain)
        snow_mm = data.get("snow", {}).get("1h", 0)
        if snow_mm > 0:
            score += min(snow_mm * 3, 6)

        # Visibility impact
        visibility_m = data.get("visibility", 10000)
        visibility_km = visibility_m / 1000
        if visibility_km < 5:
            score += (5 - visibility_km) * 0.8

        # Wind impact
        wind_speed = data.get("wind", {}).get("speed", 0) * 3.6  # m/s to km/h
        if wind_speed > 40:
            score += min((wind_speed - 40) / 10, 3)

        # Temperature extremes
        temp = data.get("main", {}).get("temp", 293) - 273.15
        if temp < -5 or temp > 40:
            score += 1.5
        elif temp < 0 or temp > 35:
            score += 0.8

        # Weather condition codes
        weather_code = data.get("weather", [{}])[0].get("id", 800)
        # Thunderstorm
        if 200 <= weather_code < 300:
            score += 3
        # Drizzle
        elif 300 <= weather_code < 400:
            score += 1
        # Rain
        elif 500 <= weather_code < 600:
            score += 2
        # Snow
        elif 600 <= weather_code < 700:
            score += 2.5
        # Atmosphere (fog, mist, haze)
        elif 700 <= weather_code < 800:
            score += 1.5

        return round(min(score, 10), 1)

    def _to_weather_condition(self, data: Dict[str, Any]) -> WeatherCondition:
        return WeatherCondition(
            temperature=round(data["main"]["temp"], 1),
            humidity=data["main"]["humidity"],
            visibility=round(data.get("visibility", 10000) / 1000, 1),
            rainfall=round(data.get("rain", {}).get("1h", 0), 1),
            wind_speed=round(data.get("wind", {}).get("speed", 0) * 3.6, 1),
            condition=data["weather"][0]["description"].title(),
            impact_score=self._calculate_impact_score(data),
        )

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type((httpx.TransportError, httpx.HTTPStatusError)),
        reraise=True,
    )
    async def _fetch_weather(self, coords: Coordinates) -> Dict[str, Any]:
        params: Dict[str, Any] = {
            "lat": coords.lat,
            "lon": coords.lon,
            "appid": self.api_key,
            "units": "metric",
        }
        response = await self.client.get(f"{self.BASE_URL}/weather", params=params)
        response.raise_for_status()
        return response.json()

    async def get_weather(self, coords: Coordinates) -> WeatherCondition:
        """Fetch real weather data from OpenWeatherMap (cached + retried)."""
        if not self.api_key:
            raise ValueError(
                "OpenWeatherMap API key is required. "
                "Get a free key at https://openweathermap.org/api "
                "and set OPENWEATHER_API_KEY in your .env file."
            )

        cache_key = self._get_cache_key(coords.lat, coords.lon)

        # Check shared cache (Redis or in-memory)
        cached = await cache.get_json(cache_key)
        if cached is not None:
            return WeatherCondition(**cached)

        try:
            data = await self._fetch_weather(coords)
        except httpx.HTTPStatusError as exc:
            # Don't retry 4xx client errors (bad key, bad params)
            if exc.response.status_code < 500:
                raise ValueError(
                    f"OpenWeatherMap request failed ({exc.response.status_code}). "
                    "Check your OPENWEATHER_API_KEY."
                ) from exc
            raise
        except httpx.TransportError as exc:
            raise ValueError(
                "Unable to reach OpenWeatherMap. Please try again shortly."
            ) from exc

        weather = self._to_weather_condition(data)
        await cache.set_json(cache_key, weather.model_dump(), settings.weather_cache_ttl)
        return weather

    async def close(self) -> None:
        await self.client.aclose()