"""Production weather data service using OpenWeatherMap API."""
import httpx
from typing import Dict, Any
from datetime import datetime, timedelta, timezone

from ..models.schemas import WeatherCondition, Coordinates
from ..core.config import settings


class WeatherService:
    """Production weather service using OpenWeatherMap API."""

    BASE_URL = "https://api.openweathermap.org/data/2.5"

    def __init__(self):
        self.api_key = settings.openweather_api_key
        self.client = httpx.AsyncClient(timeout=15.0)
        self._cache: Dict[str, tuple[WeatherCondition, datetime]] = {}

    def _get_cache_key(self, lat: float, lon: float) -> str:
        return f"{round(lat, 2)}:{round(lon, 2)}"

    def _is_cache_valid(self, cached_time: datetime) -> bool:
        return datetime.now(timezone.utc) - cached_time < timedelta(seconds=settings.weather_cache_ttl)

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

    async def get_weather(self, coords: Coordinates) -> WeatherCondition:
        """Fetch real weather data from OpenWeatherMap."""
        if not self.api_key:
            raise ValueError(
                "OpenWeatherMap API key is required. "
                "Get a free key at https://openweathermap.org/api "
                "and set OPENWEATHER_API_KEY in your .env file."
            )

        cache_key = self._get_cache_key(coords.lat, coords.lon)

        # Check cache
        if cache_key in self._cache:
            weather, cached_time = self._cache[cache_key]
            if self._is_cache_valid(cached_time):
                return weather

        # Fetch from real API
        params: dict[str, float | str] = {
            "lat": coords.lat,
            "lon": coords.lon,
            "appid": self.api_key,
            "units": "metric"
        }

        response = await self.client.get(f"{self.BASE_URL}/weather", params=params)
        response.raise_for_status()
        data = response.json()

        weather = WeatherCondition(
            temperature=round(data["main"]["temp"], 1),
            humidity=data["main"]["humidity"],
            visibility=round(data.get("visibility", 10000) / 1000, 1),
            rainfall=round(data.get("rain", {}).get("1h", 0), 1),
            wind_speed=round(data.get("wind", {}).get("speed", 0) * 3.6, 1),
            condition=data["weather"][0]["description"].title(),
            impact_score=self._calculate_impact_score(data)
        )

        self._cache[cache_key] = (weather, datetime.now(timezone.utc))
        return weather

    async def close(self):
        await self.client.aclose()