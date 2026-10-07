"""FastAPI application entry point."""
import logging
import time
from collections import defaultdict
from contextlib import asynccontextmanager
from contextlib import asynccontextmanager
from datetime import datetime, timezone

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .core.config import settings
from .routers import routes_router
from .services.cache import cache

logging.basicConfig(
    level=logging.DEBUG if settings.debug else logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


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
    """Startup/shutdown: validate config and manage the shared cache."""
    logger.info("🚀 Starting %s", settings.app_name)

    # Critical issue fix: warn loudly about missing API keys at startup
    # instead of failing mysteriously on the first request.
    missing = []
    if not settings.openweather_api_key:
        missing.append("OPENWEATHER_API_KEY")
    if not settings.tomtom_api_key:
        missing.append("TOMTOM_API_KEY")
    if missing:
        logger.warning(
            "⚠️  Missing API keys: %s — related features will fail at request time. "
            "See backend/.env.example for how to get free keys.",
            ", ".join(missing),
        )
    if not settings.openroute_api_key:
        logger.info("ℹ️  OPENROUTE_API_KEY not set — cycling/walking modes fall back to OSRM driving.")

    await cache.connect()
    logger.info("Cache backend: %s", cache.backend)

    yield

    await cache.close()
    logger.info("👋 Shutting down gracefully")
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
    description="Intelligent route optimization with traffic, weather, multi-stop and multi-mode routing.",
    version="1.1.0",
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
    allow_origins=[str(o) for o in settings.cors_origins],
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
    expose_headers=["*"],
)
app.add_middleware(SecurityHeadersMiddleware)

# ─── Simple in-memory rate limiter ─────────────────────────
_RATE_EXEMPT_PATHS = {"/", "/health", "/metrics", "/docs", "/redoc", "/openapi.json"}


class RateLimitMiddleware:
    """Sliding-window rate limiter (per client IP). No extra deps."""

    def __init__(self, app, max_requests: int, window_seconds: int):
        self.app = app
        self.max_requests = max_requests
        self.window = window_seconds
        self._hits: dict[str, list[float]] = defaultdict(list)

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        path = scope.get("path", "")
        if path in _RATE_EXEMPT_PATHS or path.startswith(("/docs", "/redoc", "/openapi")):
            await self.app(scope, receive, send)
            return

        ip = "unknown"
        for key, value in scope.get("headers", []):
            if key == b"x-forwarded-for":
                ip = value.decode().split(",")[0].strip()
        if ip == "unknown" and scope.get("client"):
            ip = scope["client"][0]

        now = time.monotonic()
        hits = [t for t in self._hits[ip] if now - t < self.window]
        if len(hits) >= self.max_requests:
            response = JSONResponse(
                status_code=429,
                content={"error": "Rate limit exceeded", "detail": f"Max {self.max_requests} requests per {self.window}s"},
            )
            await response(scope, receive, send)
            return
        hits.append(now)
        self._hits[ip] = hits
        await self.app(scope, receive, send)


app.add_middleware(
    RateLimitMiddleware,
    max_requests=settings.rate_limit_requests,
    window_seconds=settings.rate_limit_window_seconds,
)

# ─── Hand-rolled Prometheus-style metrics (no extra deps) ──
_metrics = {
    "requests_total": 0,
    "optimize_requests_total": 0,
    "errors_total": 0,
    "rate_limited_total": 0,
}


@app.middleware("http")
async def metrics_middleware(request: Request, call_next):
    _metrics["requests_total"] += 1
    if request.url.path.endswith("/routes/optimize"):
        _metrics["optimize_requests_total"] += 1
    try:
        response = await call_next(request)
        if response.status_code >= 500:
            _metrics["errors_total"] += 1
        return response
    except Exception:
        _metrics["errors_total"] += 1
        raise


app.include_router(routes_router, prefix="/api/v1")


@app.get("/", tags=["health"])
async def root():
    return {
        "status": "ok",
        "service": settings.app_name,
        "version": "1.1.0",
        "cache_backend": cache.backend,
        "docs": "/docs"
        "version": "1.0.0",
        "docs": "/docs",
    }


@app.get("/health", tags=["health"])
async def health_check():
    """Detailed health check with live dependency status."""
    return {
        "status": "healthy",
        "version": "1.1.0",
        "cache_backend": cache.backend,
        "api_keys_configured": {
            "openweather": bool(settings.openweather_api_key),
            "tomtom": bool(settings.tomtom_api_key),
            "openroute": bool(settings.openroute_api_key),
        },
        "services": {
            "routing_engine": "ok",
            "weather_api": "configured" if settings.openweather_api_key else "missing_key",
            "traffic_api": "configured" if settings.tomtom_api_key else "missing_key",
            "cache": cache.backend,
        }
    }


@app.get("/metrics", tags=["monitoring"])
async def metrics():
    """Prometheus-compatible text metrics."""
    lines = [
        f'tro_requests_total {_metrics["requests_total"]}',
        f'tro_optimize_requests_total {_metrics["optimize_requests_total"]}',
        f'tro_errors_total {_metrics["errors_total"]}',
        f'tro_rate_limited_total {_metrics["rate_limited_total"]}',
    ]
    return Response(content="\n".join(lines), media_type="text/plain")
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
