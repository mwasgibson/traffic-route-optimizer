"""API routes for route optimization using real geocoding data."""
import hashlib
import logging
import re
from typing import Any, List, Optional, Dict

import httpx
from fastapi import APIRouter, HTTPException, Query, Request, Response, status
from fastapi.responses import JSONResponse
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from xml.sax.saxutils import escape

from ..core.config import settings
from ..models.schemas import (
    RouteRequest, RouteOptimizationResponse, TrafficHeatmapResponse,
    Coordinates, LocationSearchResult, ErrorResponse, GpxExportRequest
)
from ..services.route_optimizer import RouteOptimizer
from ..services.traffic_service import TrafficService
from ..services.cache import cache

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/routes", tags=["routes"])

NOMINATIM_BASE = "https://nominatim.openstreetmap.org"

_nominatim_client: Optional[httpx.AsyncClient] = None


def _get_nominatim_client() -> httpx.AsyncClient:
    global _nominatim_client
    if _nominatim_client is None or _nominatim_client.is_closed:
        _nominatim_client = httpx.AsyncClient(
            timeout=settings.http_timeout_seconds,
            headers={
                "User-Agent": "TrafficRouteOptimizerApp/1.1 (contact: admin@trafficoptimizer.local)",
                "Accept-Language": "en-US,en;q=0.9"
            }
        )
    return _nominatim_client


def _sanitize_query(q: str) -> str:
    """Strip control characters and limit length to prevent injection/abuse."""
    cleaned = re.sub(r'[\x00-\x1f<>"]', " ", q)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned[: settings.max_search_query_length]


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    retry=retry_if_exception_type(httpx.TransportError),
    reraise=True,
)
async def _nominatim_get(path: str, params: Dict[str, Any]) -> httpx.Response:
    client = _get_nominatim_client()
    response = await client.get(f"{NOMINATIM_BASE}{path}", params=params)
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
        500: {"model": ErrorResponse, "description": "Internal server error"}
    },
    summary="Optimize routes (multi-stop, multi-mode)",
    description="""
    Find the optimal route between origin and destination, with optional
    ordered intermediate waypoints (multi-stop) and transport mode
    (driving / cycling / walking). Considers real-time traffic, weather,
    travel time, distance, safety and fuel efficiency.
    """
)
async def optimize_routes(request: RouteRequest):
    """Optimize routes with multi-factor analysis."""
    optimizer = RouteOptimizer()
    try:
        result = await optimizer.optimize_routes(
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
            avoid_highways=request.avoid_highways
        )
        return result
    except ValueError as ve:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(ve))
    except Exception as e:
        logger.exception("Route optimization failed")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Route optimization error: {str(e)}"
        )
    finally:
        await optimizer.close()


@router.post(
    "/export/gpx",
    summary="Export a route as GPX",
    description="Generate a GPX 1.1 file from a route path and optional waypoints."
)
async def export_gpx(request: GpxExportRequest) -> Response:
    """Export route geometry as a downloadable GPX file."""
    try:
        wpts = "\n".join(
            f'    <wpt lat="{c.lat}" lon="{c.lon}"><name>Stop {i + 1}</name></wpt>'
            for i, c in enumerate(request.waypoints)
        )
        trkpts = "\n".join(
            f'        <trkpt lat="{c.lat}" lon="{c.lon}"></trkpt>'
            for c in request.route
        )
        gpx = f'''<?xml version="1.0" encoding="UTF-8"?>
<gpx version="1.1" creator="TrafficRouteOptimizer" xmlns="http://www.topografix.com/GPX/1/1">
  <metadata><name>{escape(request.name)}</name></metadata>
{wpts}
  <trk><name>{escape(request.name)}</name>
    <trkseg>
{trkpts}
    </trkseg>
  </trk>
</gpx>'''
        return Response(
            content=gpx,
            media_type="application/gpx+xml",
            headers={"Content-Disposition": 'attachment; filename="route.gpx"'}
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"GPX export failed: {str(e)}")


@router.get("/heatmap", response_model=TrafficHeatmapResponse)
async def get_traffic_heatmap(
    north: float = Query(..., description="Northern boundary latitude"),
    south: float = Query(..., description="Southern boundary latitude"),
    east: float = Query(..., description="Eastern boundary longitude"),
    west: float = Query(..., description="Western boundary longitude")
):
    """Get traffic heatmap for bounding box."""
    try:
        service = TrafficService()
        result = await service.get_traffic_heatmap(north, south, east, west)
        await service.close()
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/search", response_model=List[LocationSearchResult])
async def search_locations(
    q: str = Query(..., min_length=2, description="Search query"),
    limit: int = Query(6, ge=1, le=20)
):
    """Search for locations by name using Nominatim (sanitized + cached)."""
    query = _sanitize_query(q)
    if len(query) < 2:
        raise HTTPException(status_code=422, detail="Query too short after sanitization")

    cache_key = f"geocode:{hashlib.sha256(f'{query}:{limit}'.encode()).hexdigest()[:24]}"
    cached = await cache.get_json(cache_key)
    if cached is not None:
        return [LocationSearchResult(**item) for item in cached]

    try:
        params: Dict[str, Any] = {
            "q": query, "format": "jsonv2", "limit": limit,
            "addressdetails": 1, "namedetails": 1, "extratags": 0,
        }
        response = await _nominatim_get("/search", params)
        data = response.json()

        results: List[LocationSearchResult] = []
        for item in data:
            addr = item.get("address", {})
            address_parts = [
                str(addr[k]) for k in
                ["house_number", "road", "suburb", "city", "town", "village",
                 "county", "state", "country"] if addr.get(k)
            ]
            display_addr = item.get(
                "display_name", ", ".join(address_parts) if address_parts else "Unknown"
            )
            results.append(LocationSearchResult(
                place_id=str(item.get("place_id", "")),
                name=item.get("name") or item.get("display_name", "").split(",")[0].strip(),
                address=display_addr,
                coordinates=Coordinates(lat=float(item["lat"]), lon=float(item["lon"])),
                type=item.get("type", item.get("category", "unknown"))
            ))

        await cache.set_json(
            cache_key, [r.model_dump() for r in results], settings.geocode_cache_ttl
        )
        return results

    except httpx.HTTPStatusError as e:
        if e.response.status_code == 429:
            raise HTTPException(
                status_code=429,
                detail="Rate limited by geocoding service. Please wait and try again."
            )
        raise HTTPException(status_code=502, detail=f"Geocoding service error: {e.response.status_code}")
    except httpx.RequestError:
        raise HTTPException(status_code=503, detail="Unable to reach geocoding service.")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Search failed: {str(e)}")


@router.get("/reverse-geocode", response_model=LocationSearchResult)
async def reverse_geocode(
    lat: float = Query(..., ge=-90, le=90, description="Latitude"),
    lon: float = Query(..., ge=-180, le=180, description="Longitude")
):
    """Reverse geocode coordinates to address using Nominatim (cached)."""
    cache_key = f"reverse:{round(lat, 5)}:{round(lon, 5)}"
    cached = await cache.get_json(cache_key)
    if cached is not None:
        return LocationSearchResult(**cached)

    try:
        params: Dict[str, Any] = {
            "lat": lat, "lon": lon, "format": "jsonv2",
            "addressdetails": 1, "zoom": 18,
        }
        response = await _nominatim_get("/reverse", params)
        data = response.json()

        if "error" in data:
            raise HTTPException(status_code=404, detail=data["error"])

        addr = data.get("address", {})
        address_parts = [
            str(addr[k]) for k in
            ["house_number", "road", "suburb", "city", "town", "village",
             "county", "state", "country"] if addr.get(k)
        ]
        display_addr = data.get(
            "display_name", ", ".join(address_parts) if address_parts else "Unknown location"
        )
        result = LocationSearchResult(
            place_id=str(data.get("place_id", "")),
            name=data.get("name") or display_addr.split(",")[0].strip(),
            address=display_addr,
            coordinates=Coordinates(lat=lat, lon=lon),
            type=data.get("type", data.get("category", "detected"))
        )
        await cache.set_json(
            cache_key, result.model_dump(), settings.geocode_cache_ttl
        )
        return result

    except httpx.HTTPStatusError as e:
        if e.response.status_code == 429:
            raise HTTPException(status_code=429, detail="Rate limited by geocoding service.")
        raise HTTPException(status_code=502, detail=f"Geocoding service error: {e.response.status_code}")
    except httpx.RequestError:
        raise HTTPException(status_code=503, detail="Unable to reach geocoding service.")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Reverse geocoding failed: {str(e)}")