import { useState, useCallback } from "react";
import { Map, Navigation, Activity, Download } from "lucide-react";
import { ErrorBoundary } from "@/components/ErrorBoundary";
import { TurnByTurnPanel } from "@/components/TurnbyTurnPanel";
import { buildGpx, downloadGpx } from "@/utils/gpx";
import { RouteMap } from "@/components/RouteMap";
import { RoutePanel } from "@/components/RoutePanel";
import { RouteComparison } from "@/components/RouteComparison";
import { TrafficDensityChart } from "@/components/TrafficDensityChart";
import { AIInsights } from "@/components/AIInsights";
import { CostAnalysis } from "@/components/CostAnalysis";
import { useRouteOptimization } from "@/hooks/useRouteOptimization";
import type { Coordinates } from "@/types";

export function Dashboard() {
  const { data, loading, error, optimize, reset } = useRouteOptimization();
  const [activeRouteId, setActiveRouteId] = useState<string | null>(null);
  const [mapBounds, setMapBounds] = useState<{
    origin: Coordinates;
    destination: Coordinates;
  } | null>(null);

  const handleOptimize = useCallback(
    async (params: {
      origin: Coordinates;
      destination: Coordinates;
      timeWeight: number;
      distanceWeight: number;
      safetyWeight: number;
      fuelWeight: number;
      vehicleType: string;
      avoidTolls: boolean;
      avoidHighways: boolean;
      waypoints: Coordinates[];
      transportMode: "driving" | "cycling" | "walking";
    }) => {
      setMapBounds({ origin: params.origin, destination: params.destination });
      setMapWaypoints(params.waypoints);
      setActiveRouteId(null);

      await optimize({
        origin: params.origin,
        destination: params.destination,
        time_weight: params.timeWeight,
        distance_weight: params.distanceWeight,
        safety_weight: params.safetyWeight,
        fuel_weight: params.fuelWeight,
        vehicle_type: params.vehicleType,
        avoid_tolls: params.avoidTolls,
        avoid_highways: params.avoidHighways,
        waypoints: params.waypoints,
        transport_mode: params.transportMode,
      });
    },
    [optimize],
  );

  const [mapWaypoints, setMapWaypoints] = useState<Coordinates[]>([]);

  const handleReset = useCallback(() => {
    reset();
    setActiveRouteId(null);
    setMapBounds(null);
  }, [reset]);

  return (
    <div className="flex flex-col h-screen bg-slate-950 text-white font-sans overflow-hidden">
      {/* Header */}
      <header className="bg-slate-900 border-b border-slate-800 px-5 py-3 flex items-center justify-between shrink-0 z-10">
        <div className="flex items-center gap-3">
          <div className="w-9 h-9 rounded-lg bg-emerald-500/20 flex items-center justify-center border border-emerald-500/30">
            <Navigation className="w-5 h-5 text-emerald-400" />
          </div>
          <div>
            <h1 className="text-lg font-bold text-white leading-tight">
              Traffic Route Optimizer
            </h1>
            <p className="text-xs text-slate-400">
              Smart routing with traffic & weather intelligence
            </p>
          </div>
        </div>

        <div className="flex items-center gap-3">
          {data && (
            <button
              onClick={handleReset}
              className="bg-slate-700 hover:bg-slate-600 text-slate-300 font-medium py-2 px-4 rounded-lg transition-all text-sm"
            >
              New Search
            </button>
          )}
          {data && (
            <button
              onClick={() => {
                const route =
                  data.routes.find((r) => r.route_id === activeRouteId) ??
                  data.routes.find(
                    (r) => r.route_id === data.recommended_route_id,
                  );
                if (!route) return;
                downloadGpx(
                  `${route.name.replace(/\s+/g, "_")}.gpx`,
                  buildGpx(
                    `${route.name} — Traffic Route Optimizer`,
                    route.path,
                    mapWaypoints,
                  ),
                );
              }}
              className="bg-slate-700 hover:bg-slate-600 text-slate-300 font-medium py-2 px-4 rounded-lg transition-all text-sm flex items-center gap-2"
            >
              <Download className="w-4 h-4" />
              GPX
            </button>
          )}
          <div className="flex items-center gap-2">
            <span className="text-xs text-slate-400">Status:</span>
            <span className="flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-emerald-500/15 border border-emerald-500/30 text-emerald-400 text-xs font-medium">
              <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse"></span>
              {loading ? "Processing" : "Active"}
            </span>
          </div>
        </div>
      </header>

      {/* Error Banner */}
      {error && (
        <div className="bg-red-500/10 border-b border-red-500/30 px-5 py-2 text-red-400 text-sm flex items-center gap-2">
          <Activity className="w-4 h-4" />
          {error}
        </div>
      )}

      {/* Main Content */}
      <div className="flex-1 flex overflow-hidden">
        {/* Left Panel */}
        <RoutePanel
          data={data}
          activeRouteId={activeRouteId}
          onRouteSelect={setActiveRouteId}
          onOptimize={handleOptimize}
          loading={loading}
        />

        {/* Center + Right */}
        <div className="flex-1 flex flex-col">
          {data && mapBounds ? (
            <>
              {/* Map */}
              <div className="flex-1 min-h-0">
                <ErrorBoundary>
                  <RouteMap
                    routes={data.routes}
                    origin={mapBounds.origin}
                    destination={mapBounds.destination}
                    waypoints={mapWaypoints}
                    activeRouteId={activeRouteId}
                  />
                </ErrorBoundary>
              </div>

              {/* Bottom Comparison */}
              <div className="h-64 bg-slate-900 border-t border-slate-800 overflow-y-auto shrink-0">
                <div className="p-4">
                  <RouteComparison routes={data.routes} />
                </div>
              </div>
            </>
          ) : (
            /* Empty State */
            <div className="flex-1 flex items-center justify-center">
              <div className="text-center">
                <div className="w-20 h-20 bg-slate-800 rounded-2xl flex items-center justify-center mx-auto mb-4 border border-slate-700">
                  <Map className="w-10 h-10 text-slate-600" />
                </div>
                <h2 className="text-xl font-bold text-slate-300 mb-2">
                  Ready to Optimize
                </h2>
                <p className="text-sm text-slate-500 max-w-md mx-auto mb-6">
                  Search for your origin and destination, adjust optimization
                  weights, select your vehicle type, then click "Optimize
                  Routes" to get intelligent recommendations.
                </p>
                <div className="flex items-center justify-center gap-2 text-xs text-slate-500">
                  <span className="px-2 py-1 rounded bg-slate-800 border border-slate-700">
                    1. Search locations
                  </span>
                  <span className="text-slate-600">→</span>
                  <span className="px-2 py-1 rounded bg-slate-800 border border-slate-700">
                    2. Adjust weights
                  </span>
                  <span className="text-slate-600">→</span>
                  <span className="px-2 py-1 rounded bg-slate-800 border border-slate-700">
                    3. Optimize
                  </span>
                </div>
              </div>
            </div>
          )}
        </div>

        {/* Right Panel */}
        {data && (
          <div className="w-72 bg-slate-800/50 border-l border-slate-700 flex flex-col overflow-y-auto">
            <TurnByTurnPanel
              route={
                data.routes.find((r) => r.route_id === activeRouteId) ??
                data.routes.find(
                  (r) => r.route_id === data.recommended_route_id,
                ) ??
                null
              }
            />
            <AIInsights
              routes={data.routes}
              recommendedRouteId={data.recommended_route_id}
            />
            <TrafficDensityChart />
            <CostAnalysis routes={data.routes} />
          </div>
        )}
      </div>
    </div>
  );
}
