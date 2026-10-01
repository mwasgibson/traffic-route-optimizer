"""FastAPI application entry point."""
from contextlib import asynccontextmanager
from datetime import datetime, timezone

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from .core.config import settings
from .routers import routes_router


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Attach baseline security headers to every response."""

    async def dispatch(self, request: Request, call_next) -> Response:
        response = await call_next(request)
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        response.headers.setdefault(
            "Permissions-Policy",
            "geolocation=(self), microphone=(), camera=()",
        )
        # API is JSON-only; CSP is intentionally minimal
        response.headers.setdefault(
            "Content-Security-Policy",
            "default-src 'none'; frame-ancestors 'none'",
        )
        return response


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler."""
    print(f"Starting {settings.app_name}")
    print(f"  Debug mode: {settings.debug}")
    weather_ready = bool(settings.openweather_api_key)
    traffic_ready = bool(settings.tomtom_api_key)
    print(f"  OpenWeatherMap key: {'set' if weather_ready else 'MISSING'}")
    print(f"  TomTom key: {'set' if traffic_ready else 'MISSING'}")
    yield
    print("Shutting down gracefully")


app = FastAPI(
    title=settings.app_name,
    description="""
    Intelligent route optimization system that combines traffic conditions,
    weather data, and route analysis to recommend the most efficient path.

    ## Features

    - **Multi-factor Optimization**: time, distance, safety, fuel, and weather
    - **Real-time Traffic**: live congestion data (TomTom)
    - **Weather Integration**: current conditions and impact assessment
    - **AI Insights**: recommendations and warnings
    - **Traffic Heatmaps**: visual congestion mapping

    ## Data Sources

    - OpenWeatherMap (weather)
    - TomTom Traffic API (traffic)
    - OSRM (road geometry; public demo instance)
    - OpenStreetMap / Nominatim (geocoding)
    """,
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
    expose_headers=["*"],
)
app.add_middleware(SecurityHeadersMiddleware)

# Include routers
app.include_router(routes_router, prefix="/api/v1")


@app.get("/", tags=["health"])
async def root():
    """Health check endpoint."""
    return {
        "status": "ok",
        "service": settings.app_name,
        "version": "1.0.0",
        "docs": "/docs",
    }


@app.get("/health", tags=["health"])
async def health_check() -> dict:
    """Detailed health check with real timestamp and key presence."""
    weather_configured = bool(settings.openweather_api_key)
    traffic_configured = bool(settings.tomtom_api_key)

    services = {
        "routing_engine": "ok",  # OSRM public; no local key
        "weather_api": "configured" if weather_configured else "missing_api_key",
        "traffic_api": "configured" if traffic_configured else "missing_api_key",
    }
    all_ready = weather_configured and traffic_configured
    return {
        "status": "healthy" if all_ready else "degraded",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "services": services,
    }
