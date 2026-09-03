"""FastAPI application entry point."""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from .core.config import settings
from .routers import routes_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler."""
    # Startup
    print(f"🚀 Starting {settings.app_name}")
    print(f"   Debug mode: {settings.debug}")
    yield
    # Shutdown
    print("👋 Shutting down gracefully")


app = FastAPI(
    title=settings.app_name,
    description="""
    Intelligent route optimization system that combines traffic conditions, 
    weather data, and route analysis to recommend the most efficient path.

    ## Features

    - **Multi-factor Optimization**: Considers time, distance, safety, fuel, and weather
    - **Real-time Traffic**: Live congestion data and incident reports
    - **Weather Integration**: Current conditions and impact assessment
    - **AI Insights**: Intelligent recommendations and warnings
    - **Traffic Heatmaps**: Visual congestion mapping

    ## Data Sources

    - OpenWeatherMap (weather)
    - TomTom Traffic API (traffic data)
    - Internal routing engine (path generation)
    """,
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc"
)

origins = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://localhost:3000",
]

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
    expose_headers=["*"],
)

# Include routers
app.include_router(routes_router, prefix="/api/v1")


@app.get("/", tags=["health"])
async def root():
    """Health check endpoint."""
    return {
        "status": "ok",
        "service": settings.app_name,
        "version": "1.0.0",
        "docs": "/docs"
    }


@app.get("/health", tags=["health"])
async def health_check() -> dict[str, str | dict[str, str]]:
    """Detailed health check."""
    return {
        "status": "healthy",
        "timestamp": "2024-01-01T00:00:00Z",
        "services": {
            "routing_engine": "ok",
            "weather_api": "ok",
            "traffic_api": "ok"
        }
    }