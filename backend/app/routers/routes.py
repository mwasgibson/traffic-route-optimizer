"""API routes for route optimization and geocoding."""
import hashlib
import logging
import re
from typing import Any, Dict, List, Optional

import httpx
from fastapi import APIRouter, HTTPException, Query, Response, status
from fastapi.responses import JSONResponse
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential
from xml.sax.saxutils import escape

from ..core.config import settings
from ..core.constants import NOMINATIM_BASE_URL, NOMINATIM_USER_AGENT
from ..models.schemas import (
    Coordinates,
    ErrorResponse,
    GpxExportRequest,
    LocationSearchResult,
    RouteOptimizationResponse,
    RouteRequest,
    TrafficHeatmapResponse,
)
from ..services.cache import cache
from ..services.route_optimizer import RouteOptimizer
from ..services.traffic_service import TrafficService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/routes", tags=["routes"])

_nominatim_client: Optional[httpx.AsyncClient] = None


def _get_nominatim_client() -> httpx.AsyncClient:
    global _nominatim_client
    if _nominatim_client is None or _nominatim_client.is_closed:
        _nominatim_client = httpx.AsyncClient(
            timeout=settings.http_timeout_seconds,
            headers={
                "User-Agent": NOMINATIM_USER_AGENT,
                "Accept-Language": "en-US,en;q=0.9",
            },
        )
    return _nominatim_client


def _sanitize_query(q: str) -> str:
    """Strip control characters and limit length to prevent injection or abuse."""
    cleaned = re.sub(r'[\x00-\x1f<>"]', " ", q)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned[: settings.max_search_query_length]


def _display_address(data: Dict[str, Any], fallback: str) -> str:
    address = data.get("address", {})
    keys = (
        "house_number",
        "road",
        "suburb",
        "city",
        "town",
        "village",
        "county",
        "state",
        "country",
    )
    parts = [str(address[key]) for key in keys if address.get(key)]
    return data.get(
        "display_name",
        ", ".join(parts) if parts else fallback,
    )


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    retry=retry_if_exception_type(httpx.TransportError),
    reraise=True,
)
async def _nominatim_get(path: str, params: Dict[str, Any]) -> httpx.Response:
    client = _get_nominatim_client()
    response = await client.get(f"{NOMINATIM_BASE_URL}{path}", params=params)
    response.raise_for_status()
    return response


@router.options("/optimize")
async def optimize_routes_options():
    return JSONResponse(content={"status": "ok"}, status_code=status.HTTP_200_OK)


@router.post(
    "/optimize",
    response_model=RouteOptimizationResponse,
    responses={
        400: {"model": ErrorResponse, "description": "Invalid request"},
        500: {"model": ErrorResponse, "description": "Internal server error"},
    },
    summary="Optimize routes (multi-stop, multi-mode)",
    description=(
        "Find the optimal route between origin and destination, with optional "
        "ordered intermediate waypoints (multi-stop) and transport mode "
        "(driving / cycling / walking). Considers real-time traffic, weather, "
        "travel time, distance, safety and fuel efficiency."
    ),
)
async def optimize_routes(request: RouteRequest) -> RouteOptimizationResponse:
    """Optimize routes with multi-factor analysis."""
    optimizer = RouteOptimizer()
    try:
        return await optimizer.optimize_routes(
            origin=request.origin,
            destination=request.destination,
            waypoints=request.waypoints,
            time_weight=request.time_weight,
            distance_weight=request.distance_weight,
            safety_weight=request.safety_weight,
            fuel_weight=request.fuel_weight,
            vehicle_type=request.vehicle_type,
            transport_mode=request.transport_mode,
            avoid_tolls=request.avoid_tolls,
            avoid_highways=request.avoid_highways,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    except Exception as exc:
        logger.exception("Route optimization failed")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Route optimization error: {exc!s}",
        ) from exc
    finally:
        await optimizer.close()


@router.post(
    "/export/gpx",
    summary="Export a route as GPX",
    description="Generate a GPX 1.1 file from a route path and optional waypoints.",
)
async def export_gpx(request: GpxExportRequest) -> Response:
    """Export route geometry as a downloadable GPX file."""
    waypoints = "\n".join(
        f'    <wpt lat="{point.lat}" lon="{point.lon}">'
        f"<name>Stop {index + 1}</name></wpt>"
        for index, point in enumerate(request.waypoints)
    )
    track_points = "\n".join(
        f'        <trkpt lat="{point.lat}" lon="{point.lon}"></trkpt>'
        for point in request.route
    )
    gpx = f"""<?xml version="1.0" encoding="UTF-8"?>
<gpx version="1.1" creator="TrafficRouteOptimizer" xmlns="http://www.topografix.com/GPX/1/1">
  <metadata><name>{escape(request.name)}</name></metadata>
{waypoints}
  <trk><name>{escape(request.name)}</name>
    <trkseg>
{track_points}
    </trkseg>
  </trk>
</gpx>"""
    return Response(
        content=gpx,
        media_type="application/gpx+xml",
        headers={"Content-Disposition": 'attachment; filename="route.gpx"'},
    )


@router.get(
    "/heatmap",
    response_model=TrafficHeatmapResponse,
    summary="Get traffic heatmap for a region",
)
async def get_traffic_heatmap(
    north: float = Query(..., description="Northern boundary latitude"),
    south: float = Query(..., description="Southern boundary latitude"),
    east: float = Query(..., description="Eastern boundary longitude"),
    west: float = Query(..., description="Western boundary longitude"),
) -> TrafficHeatmapResponse:
    """Get traffic heatmap for a bounding box."""
    service = TrafficService()
    try:
        return await service.get_traffic_heatmap(north, south, east, west)
    except Exception as exc:
        logger.exception("Traffic heatmap request failed")
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    finally:
        await service.close()


@router.get(
    "/search",
    response_model=List[LocationSearchResult],
    summary="Search for locations by name",
)
async def search_locations(
    q: str = Query(..., min_length=2, description="Search query"),
    limit: int = Query(6, ge=1, le=20),
) -> List[LocationSearchResult]:
    """Search for locations by name using Nominatim (sanitized and cached)."""
    query = _sanitize_query(q)
    if len(query) < 2:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Query too short after sanitization",
        )

    cache_key = f"geocode:{hashlib.sha256(f'{query}:{limit}'.encode()).hexdigest()[:24]}"
    cached = await cache.get_json(cache_key)
    if cached is not None:
        return [LocationSearchResult(**item) for item in cached]

    params: Dict[str, Any] = {
        "q": query,
        "format": "jsonv2",
        "limit": limit,
        "addressdetails": 1,
        "namedetails": 1,
        "extratags": 0,
    }
    try:
        response = await _nominatim_get("/search", params)
        results: List[LocationSearchResult] = []
        for item in response.json():
            display_address = _display_address(item, "Unknown")
            results.append(
                LocationSearchResult(
                    place_id=str(item.get("place_id", "")),
                    name=item.get("name")
                    or item.get("display_name", "").split(",")[0].strip(),
                    address=display_address,
                    coordinates=Coordinates(
                        lat=float(item["lat"]),
                        lon=float(item["lon"]),
                    ),
                    type=item.get("type", item.get("category", "unknown")),
                )
            )
        await cache.set_json(
            cache_key,
            [result.model_dump() for result in results],
            settings.geocode_cache_ttl,
        )
        return results
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code == 429:
            raise HTTPException(
                status_code=429,
                detail="Rate limited by geocoding service. Please wait and try again.",
            ) from exc
        raise HTTPException(
            status_code=502,
            detail=f"Geocoding service error: {exc.response.status_code}",
        ) from exc
    except httpx.RequestError as exc:
        raise HTTPException(
            status_code=503,
            detail="Unable to reach geocoding service.",
        ) from exc
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Location search failed")
        raise HTTPException(
            status_code=500,
            detail=f"Search failed: {exc!s}",
        ) from exc


@router.get(
    "/reverse-geocode",
    response_model=LocationSearchResult,
    summary="Reverse geocode coordinates",
)
async def reverse_geocode(
    lat: float = Query(..., ge=-90, le=90, description="Latitude"),
    lon: float = Query(..., ge=-180, le=180, description="Longitude"),
) -> LocationSearchResult:
    """Reverse geocode coordinates to an address using Nominatim."""
    cache_key = f"reverse:{round(lat, 5)}:{round(lon, 5)}"
    cached = await cache.get_json(cache_key)
    if cached is not None:
        return LocationSearchResult(**cached)

    params: Dict[str, Any] = {
        "lat": lat,
        "lon": lon,
        "format": "jsonv2",
        "addressdetails": 1,
        "zoom": 18,
    }
    try:
        response = await _nominatim_get("/reverse", params)
        data = response.json()
        if "error" in data:
            raise HTTPException(status_code=404, detail=data["error"])

        display_address = _display_address(data, "Unknown location")
        result = LocationSearchResult(
            place_id=str(data.get("place_id", "")),
            name=data.get("name") or display_address.split(",")[0].strip(),
            address=display_address,
            coordinates=Coordinates(lat=lat, lon=lon),
            type=data.get("type", data.get("category", "detected")),
        )
        await cache.set_json(
            cache_key,
            result.model_dump(),
            settings.geocode_cache_ttl,
        )
        return result
    except HTTPException:
        raise
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code == 429:
            raise HTTPException(
                status_code=429,
                detail="Rate limited by geocoding service. Please wait and try again.",
            ) from exc
        raise HTTPException(
            status_code=502,
            detail=f"Geocoding service error: {exc.response.status_code}",
        ) from exc
    except httpx.RequestError as exc:
        raise HTTPException(
            status_code=503,
            detail="Unable to reach geocoding service.",
        ) from exc
    except Exception as exc:
        logger.exception("Reverse geocoding failed")
        raise HTTPException(
            status_code=500,
            detail=f"Reverse geocoding failed: {exc!s}",
        ) from exc