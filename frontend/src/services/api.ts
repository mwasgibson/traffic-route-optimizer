import axios from "axios";
import type {
  RouteRequest,
  RouteOptimizationResponse,
  TrafficHeatmapResponse,
  LocationSearchResult,
} from "@/types";

const API_BASE = (import.meta as any).env?.VITE_API_URL || "/api/v1";

const api = axios.create({
  baseURL: API_BASE,
  headers: {
    "Content-Type": "application/json",
  },
  timeout: 100000,
});

export const routeApi = {
  optimizeRoutes: async (
    request: RouteRequest,
  ): Promise<RouteOptimizationResponse> => {
    const { data } = await api.post<RouteOptimizationResponse>(
      "/routes/optimize",
      request,
    );
    return data;
  },

  getTrafficHeatmap: async (
    north: number,
    south: number,
    east: number,
    west: number,
  ): Promise<TrafficHeatmapResponse> => {
    const { data } = await api.get<TrafficHeatmapResponse>("/routes/heatmap", {
      params: { north, south, east, west },
    });
    return data;
  },

  /** Search locations using Nominatim (OpenStreetMap) — returns real coordinates worldwide */
  searchLocations: async (
    query: string,
    limit = 6,
  ): Promise<LocationSearchResult[]> => {
    const { data } = await api.get<LocationSearchResult[]>("/routes/search", {
      params: { q: query, limit },
    });
    return data;
  },

  /** Reverse geocode GPS coordinates to a real address using Nominatim */
  reverseGeocode: async (
    lat: number,
    lon: number,
  ): Promise<LocationSearchResult> => {
    const { data } = await api.get<LocationSearchResult>(
      "/routes/reverse-geocode",
      {
        params: { lat, lon },
      },
    );
    return data;
  },
};

export default api;
