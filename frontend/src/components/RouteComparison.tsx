import { useState } from "react";
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  RadarChart,
  PolarGrid,
  PolarAngleAxis,
  PolarRadiusAxis,
  Radar,
  Legend,
} from "recharts";
import { Table2, BarChart3, Activity } from "lucide-react";
import type { RouteAlternative } from "@/types";

interface RouteComparisonProps {
  routes: RouteAlternative[];
}

type ViewMode = "table" | "chart" | "radar";

export function RouteComparison({ routes }: RouteComparisonProps) {
  const [viewMode, setViewMode] = useState<ViewMode>("table");

  const getTrafficBadge = (condition: string) => {
    const styles: Record<string, string> = {
      light: "bg-emerald-500/15 text-emerald-400 border-emerald-500/30",
      moderate: "bg-amber-500/15 text-amber-400 border-amber-500/30",
      heavy: "bg-red-500/15 text-red-400 border-red-500/30",
      severe: "bg-red-600/15 text-red-500 border-red-600/30",
    };
    return styles[condition] || styles.light;
  };

  const getStatusBadge = (route: RouteAlternative) => {
    if (route.is_recommended) {
      return (
        <span className="px-2.5 py-1 rounded-lg bg-emerald-500/20 text-emerald-400 text-xs font-bold border border-emerald-500/30">
          RECOMMENDED
        </span>
      );
    }
    if (route.metrics.overall_score < 50) {
      return (
        <span className="px-2.5 py-1 rounded-lg bg-red-500/20 text-red-400 text-xs font-bold border border-red-500/30">
          AVOID
        </span>
      );
    }
    return (
      <span className="px-2.5 py-1 rounded-lg bg-slate-700 text-slate-400 text-xs font-medium">
        Alternative
      </span>
    );
  };

  // Chart data
  const chartData = routes.map((r) => ({
    name: r.name,
    Time: Math.max(0, 100 - (r.metrics.estimated_time_min / 60) * 100),
    Distance: Math.max(0, 100 - (r.metrics.distance_km / 30) * 100),
    Safety: r.metrics.safety_score * 10,
    Fuel: Math.max(0, 100 - (r.metrics.fuel_liters / 3) * 100),
    color: r.color,
  }));

  const radarData = [
    { metric: "Time", fullMark: 100 },
    { metric: "Distance", fullMark: 100 },
    { metric: "Safety", fullMark: 100 },
    { metric: "Fuel", fullMark: 100 },
    { metric: "Weather", fullMark: 100 },
  ].map((item, idx) => {
    const entry: Record<string, any> = { ...item };
    routes.forEach((route) => {
      const vals = [
        Math.max(0, 100 - (route.metrics.estimated_time_min / 60) * 100),
        Math.max(0, 100 - (route.metrics.distance_km / 30) * 100),
        route.metrics.safety_score * 10,
        Math.max(0, 100 - (route.metrics.fuel_liters / 3) * 100),
        Math.max(0, 100 - route.metrics.weather_impact * 10),
      ];
      entry[route.route_id] = vals[idx];
    });
    return entry;
  });

  return (
    <div className="w-full flex flex-col">
      <div className="flex items-center justify-between mb-3 px-1">
        <h2 className="text-sm font-semibold text-slate-300 flex items-center gap-2">
          <Activity className="w-4 h-4 text-indigo-400" />
          Route Analysis & Comparison
        </h2>
        <div className="flex gap-1">
          <button
            onClick={() => setViewMode("table")}
            className={`p-1.5 rounded transition-colors ${
              viewMode === "table"
                ? "bg-slate-600 text-white"
                : "text-slate-400 hover:text-white hover:bg-slate-700"
            }`}
          >
            <Table2 className="w-4 h-4" />
          </button>
          <button
            onClick={() => setViewMode("chart")}
            className={`p-1.5 rounded transition-colors ${
              viewMode === "chart"
                ? "bg-slate-600 text-white"
                : "text-slate-400 hover:text-white hover:bg-slate-700"
            }`}
          >
            <BarChart3 className="w-4 h-4" />
          </button>
          <button
            onClick={() => setViewMode("radar")}
            className={`p-1.5 rounded transition-colors ${
              viewMode === "radar"
                ? "bg-slate-600 text-white"
                : "text-slate-400 hover:text-white hover:bg-slate-700"
            }`}
          >
            <Activity className="w-4 h-4" />
          </button>
        </div>
      </div>

      {viewMode === "table" && (
        <div className="overflow-x-auto w-full">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-slate-600">
                <th className="text-left py-2 px-3 text-slate-400 font-medium">
                  Route
                </th>
                <th className="text-center py-2 px-3 text-slate-400 font-medium">
                  Distance
                </th>
                <th className="text-center py-2 px-3 text-slate-400 font-medium">
                  Est. Time
                </th>
                <th className="text-center py-2 px-3 text-slate-400 font-medium">
                  Traffic
                </th>
                <th className="text-center py-2 px-3 text-slate-400 font-medium">
                  Safety
                </th>
                <th className="text-center py-2 px-3 text-slate-400 font-medium">
                  Fuel
                </th>
                <th className="text-center py-2 px-3 text-slate-400 font-medium">
                  Weather
                </th>
                <th className="text-center py-2 px-3 text-slate-400 font-medium">
                  Score
                </th>
                <th className="text-center py-2 px-3 text-slate-400 font-medium">
                  Status
                </th>
              </tr>
            </thead>
            <tbody>
              {routes.map((route) => (
                <tr
                  key={route.route_id}
                  className="border-b border-slate-700/50 hover:bg-slate-700/30 transition-colors"
                >
                  <td className="py-3 px-3">
                    <div className="flex items-center gap-2">
                      <div
                        className="w-3 h-3 rounded-full"
                        style={{ backgroundColor: route.color }}
                      ></div>
                      <span className="font-semibold text-white">
                        {route.name}
                      </span>
                    </div>
                    <div className="text-xs text-slate-500 mt-0.5">
                      {route.description}
                    </div>
                  </td>
                  <td className="text-center py-3 px-3 text-white font-medium">
                    {route.metrics.distance_km} km
                  </td>
                  <td
                    className="text-center py-3 px-3 font-bold"
                    style={{ color: route.color }}
                  >
                    {route.metrics.estimated_time_min} min
                  </td>
                  <td className="text-center py-3 px-3">
                    <span
                      className={`px-2 py-0.5 rounded-full text-xs font-medium border ${getTrafficBadge(route.metrics.traffic_condition)}`}
                    >
                      {route.metrics.traffic_condition}
                    </span>
                  </td>
                  <td className="text-center py-3 px-3">
                    <div className="flex items-center justify-center gap-1">
                      <span
                        className="font-bold"
                        style={{
                          color:
                            route.metrics.safety_score >= 7
                              ? "#10b981"
                              : route.metrics.safety_score >= 5
                                ? "#f59e0b"
                                : "#ef4444",
                        }}
                      >
                        {route.metrics.safety_score}
                      </span>
                      <span className="text-xs text-slate-500">/10</span>
                    </div>
                  </td>
                  <td className="text-center py-3 px-3 text-white">
                    {route.metrics.fuel_liters} L
                  </td>
                  <td className="text-center py-3 px-3">
                    <span
                      className={`px-2 py-0.5 rounded-full text-xs font-medium border ${
                        route.metrics.weather_impact < 3
                          ? "bg-emerald-500/15 text-emerald-400 border-emerald-500/30"
                          : route.metrics.weather_impact < 6
                            ? "bg-amber-500/15 text-amber-400 border-amber-500/30"
                            : "bg-red-500/15 text-red-400 border-red-500/30"
                      }`}
                    >
                      {route.metrics.weather_impact < 3
                        ? "Low"
                        : route.metrics.weather_impact < 6
                          ? "Medium"
                          : "High"}
                    </span>
                  </td>
                  <td className="text-center py-3 px-3">
                    <div className="flex items-center justify-center gap-1">
                      <div className="w-16 h-2 bg-slate-700 rounded-full overflow-hidden">
                        <div
                          className="h-full rounded-full transition-all"
                          style={{
                            width: `${route.metrics.overall_score}%`,
                            backgroundColor: route.color,
                          }}
                        />
                      </div>
                      <span
                        className="font-bold text-sm"
                        style={{ color: route.color }}
                      >
                        {route.metrics.overall_score}
                      </span>
                    </div>
                  </td>
                  <td className="text-center py-3 px-3">
                    {getStatusBadge(route)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {viewMode === "chart" && (
        <div className="w-full h-[260px] pt-2">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart
              data={chartData}
              margin={{ top: 10, right: 20, left: 0, bottom: 20 }}
            >
              <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
              <XAxis dataKey="name" tick={{ fill: "#94a3b8", fontSize: 12 }} />
              <YAxis tick={{ fill: "#94a3b8", fontSize: 12 }} />
              <Tooltip
                contentStyle={{
                  backgroundColor: "#1e293b",
                  border: "1px solid #475569",
                  borderRadius: "8px",
                }}
                labelStyle={{ color: "#e2e8f0" }}
                itemStyle={{ color: "#e2e8f0" }}
              />
              <Bar dataKey="Time" fill="#3b82f6" radius={[4, 4, 0, 0]} />
              <Bar dataKey="Distance" fill="#a855f7" radius={[4, 4, 0, 0]} />
              <Bar dataKey="Safety" fill="#10b981" radius={[4, 4, 0, 0]} />
              <Bar dataKey="Fuel" fill="#f59e0b" radius={[4, 4, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      )}

      {viewMode === "radar" && (
        <div className="w-full h-[260px] pt-2">
          <ResponsiveContainer width="100%" height="100%">
            <RadarChart
              data={radarData}
              margin={{ top: 10, right: 30, bottom: 10, left: 30 }}
            >
              <PolarGrid stroke="#334155" />
              <PolarAngleAxis
                dataKey="metric"
                tick={{ fill: "#94a3b8", fontSize: 11 }}
              />
              <PolarRadiusAxis tick={{ fill: "#64748b", fontSize: 10 }} />
              {routes.map((route) => (
                <Radar
                  key={route.route_id}
                  name={route.name}
                  dataKey={route.route_id}
                  stroke={route.color}
                  fill={route.color}
                  fillOpacity={0.2}
                  strokeWidth={2}
                />
              ))}
              <Legend wrapperStyle={{ fontSize: "12px", color: "#94a3b8" }} />
              <Tooltip
                contentStyle={{
                  backgroundColor: "#1e293b",
                  border: "1px solid #475569",
                  borderRadius: "8px",
                }}
                itemStyle={{ color: "#e2e8f0" }}
              />
            </RadarChart>
          </ResponsiveContainer>
        </div>
      )}
    </div>
  );
}
