/** Geographic coordinates */
export interface Coordinates {
  lat: number;
  lon: number;
}

/** Traffic condition levels */
export type TrafficCondition = "light" | "moderate" | "heavy" | "severe";

/** Weather data */
export interface WeatherCondition {
  temperature: number;
  humidity: number;
  visibility: number;
  rainfall: number;
  wind_speed: number;
  condition: string;
  impact_score: number;
}

/** Traffic segment data */
export interface TrafficSegment {
  segment_id: string;
  start_coords: Coordinates;
  end_coords: Coordinates;
  current_speed: number;
  free_flow_speed: number;
  congestion_level: TrafficCondition;
  delay_minutes: number;
  incident_count: number;
}

/** Route metrics */
export interface RouteMetrics {
  distance_km: number;
  estimated_time_min: number;
  fuel_liters: number;
  fuel_cost_usd: number;
  safety_score: number;
  traffic_condition: TrafficCondition;
  weather_impact: number;
  overall_score: number;
  co2_emissions_kg: number;
}

/** Single route alternative */
export interface RouteAlternative {
  route_id: string;
  name: string;
  description: string;
  color: string;
  is_recommended: boolean;
  path: Coordinates[];
  metrics: RouteMetrics;
  traffic_segments: TrafficSegment[];
  warnings: string[];
  insights: string[];
  instructions: NavigationInstruction[];
}

/** Route optimization request */
export interface RouteRequest {
  origin: Coordinates;
  destination: Coordinates;
  time_weight: number;
  distance_weight: number;
  safety_weight: number;
  fuel_weight: number;
  vehicle_type: string;
  avoid_tolls: boolean;
  avoid_highways: boolean;
  waypoints?: Coordinates[];
  transport_mode?: TransportMode;
}

/** Route optimization response */
export interface RouteOptimizationResponse {
  request_id: string;
  timestamp: string;
  origin_address: string | null;
  destination_address: string | null;
  weather: WeatherCondition;
  routes: RouteAlternative[];
  recommended_route_id: string;
  time_saved_vs_worst_min: number;
  fuel_saved_vs_worst_usd: number;
  processing_time_ms: number;
  data_sources: string[];
}

/** Traffic heatmap point */
export interface TrafficHeatmapPoint {
  lat: number;
  lon: number;
  intensity: number;
  speed: number;
}

/** Traffic heatmap response */
export interface TrafficHeatmapResponse {
  bounds: { north: number; south: number; east: number; west: number };
  points: TrafficHeatmapPoint[];
  timestamp: string;
  total_incidents: number;
}

/** Location search result */
export interface LocationSearchResult {
  place_id: string;
  name: string;
  address: string;
  coordinates: Coordinates;
  type: string;
}

/** Transport routing profiles */
export type TransportMode = "driving" | "cycling" | "walking";

/** A single turn-by-turn navigation step */
export interface NavigationInstruction {
  instruction: string;
  distance_m: number;
  duration_s: number;
  maneuver_type: string;
  street_name: string | null;
}
