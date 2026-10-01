"""API routes for route optimization and geocoding."""
from typing import Any, Dict, List, Optional

import httpx
from fastapi import APIRouter, HTTPException, Query, status
from fastapi.responses import JSONResponse

from ..core.constants import NOMINATIM_BASE_URL, NOMINATIM_USER_AGENT
from ..models.schemas import (
    Coordinates,
    ErrorResponse,
    LocationSearchResult,
    RouteOptimizationResponse,
    RouteRequest,
    TrafficHeatmapResponse,
)
from ..services.route_optimizer import RouteOptimizer
from ..services.traffic_service import TrafficService

router = APIRouter(prefix="/routes", tags=["routes"])

_nominatim_client: Optional[httpx.AsyncClient] = None


def _get_nominatim_client() -> httpx.AsyncClient:
    global _nominatim_client
    if _nominatim_client is None or _nominatim_client.is_closed:
        _nominatim_client = httpx.AsyncClient(
            timeout=15.0,
            headers={
                "User-Agent": NOMINATIM_USER_AGENT,
                "Accept-Language": "en-US,en;q=0.9",
            },
        )
    return _nominatim_client


@router.options("/optimize")
async def optimize_routes_options():
    """Explicit preflight handler for route optimization."""
    return JSONResponse(content={"status": "ok"}, status_code=status.HTTP_200_OK)


@router.post(
    "/optimize",
    response_model=RouteOptimizationResponse,
    responses={
        400: {"model": ErrorResponse, "description": "Invalid request"},
        500: {"model": ErrorResponse, "description": "Internal server error"},
    },
    summary="Optimize routes between two points",
)
async def optimize_routes(request: RouteRequest):
    """Optimize routes with multi-factor analysis."""
    optimizer = RouteOptimizer()
    try:
        result = await optimizer.optimize_routes(
            origin=request.origin,
            destination=request.destination,
            time_weight=request.time_weight,
            distance_weight=request.distance_weight,
            safety_weight=request.safety_weight,
            fuel_weight=request.fuel_weight,
            vehicle_type=request.vehicle_type,
            avoid_tolls=request.avoid_tolls,
            avoid_highways=request.avoid_highways,
        )
        return result
    except ValueError as ve:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(ve),
        ) from ve
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Route optimization error: {e!s}",
        ) from e
    finally:
        await optimizer.close()


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
):
    """Get traffic heatmap for bounding box."""
    service = TrafficService()
    try:
        return await service.get_traffic_heatmap(north, south, east, west)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e
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
):
    """Search for locations by name using Nominatim."""
    try:
        client = _get_nominatim_client()
        params: Dict[str, Any] = {
            "q": q,
            "format": "jsonv2",
            "limit": limit,
            "addressdetails": 1,
            "namedetails": 1,
            "extratags": 0,
        }

        response = await client.get(f"{NOMINATIM_BASE_URL}/search", params=params)
        response.raise_for_status()
        data = response.json()

        results: List[LocationSearchResult] = []
        for item in data:
            addr = item.get("address", {})
            address_parts: List[str] = []
            for key in [
                "house_number", "road", "suburb", "city", "town",
                "village", "county", "state", "country",
            ]:
                if addr.get(key):
                    address_parts.append(str(addr[key]))

            display_addr = item.get(
                "display_name",
                ", ".join(address_parts) if address_parts else "Unknown",
            )

            results.append(
                LocationSearchResult(
                    place_id=str(item.get("place_id", "")),
                    name=item.get("name")
                    or item.get("display_name", "").split(",")[0].strip(),
                    address=display_addr,
                    coordinates=Coordinates(
                        lat=float(item["lat"]),
                        lon=float(item["lon"]),
                    ),
                    type=item.get("type", item.get("category", "unknown")),
                )
            )

        return results

    except httpx.HTTPStatusError as e:
        if e.response.status_code == 429:
            raise HTTPException(
                status_code=429,
                detail="Rate limited by geocoding service. Please wait a moment and try again.",
            ) from e
        raise HTTPException(
            status_code=502,
            detail=f"Geocoding service error: {e.response.status_code}",
        ) from e
    except httpx.RequestError as e:
        raise HTTPException(
            status_code=503,
            detail="Unable to reach geocoding service. Please check your connection.",
        ) from e
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Search failed: {e!s}") from e


@router.get(
    "/reverse-geocode",
    response_model=LocationSearchResult,
    summary="Reverse geocode coordinates",
)
async def reverse_geocode(
    lat: float = Query(..., ge=-90, le=90, description="Latitude"),
    lon: float = Query(..., ge=-180, le=180, description="Longitude"),
):
    """Reverse geocode coordinates to address using Nominatim."""
    try:
        client = _get_nominatim_client()
        params: Dict[str, Any] = {
            "lat": lat,
            "lon": lon,
            "format": "jsonv2",
            "addressdetails": 1,
            "zoom": 18,
        }

        response = await client.get(f"{NOMINATIM_BASE_URL}/reverse", params=params)
        response.raise_for_status()
        data = response.json()

        if "error" in data:
            raise HTTPException(status_code=404, detail=data["error"])

        addr = data.get("address", {})
        address_parts: List[str] = []
        for key in [
            "house_number", "road", "suburb", "city", "town",
            "village", "county", "state", "country",
        ]:
            if addr.get(key):
                address_parts.append(str(addr[key]))

        display_addr = data.get(
            "display_name",
            ", ".join(address_parts) if address_parts else "Unknown location",
        )
        name = data.get("name") or display_addr.split(",")[0].strip()

        return LocationSearchResult(
            place_id=str(data.get("place_id", "")),
            name=name,
            address=display_addr,
            coordinates=Coordinates(lat=lat, lon=lon),
            type=data.get("type", data.get("category", "detected")),
        )

    except HTTPException:
        raise
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 429:
            raise HTTPException(
                status_code=429,
                detail="Rate limited by geocoding service. Please wait a moment and try again.",
            ) from e
        raise HTTPException(
            status_code=502,
            detail=f"Geocoding service error: {e.response.status_code}",
        ) from e
    except httpx.RequestError as e:
        raise HTTPException(
            status_code=503,
            detail="Unable to reach geocoding service. Please check your connection.",
        ) from e
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Reverse geocoding failed: {e!s}"
        ) from e
