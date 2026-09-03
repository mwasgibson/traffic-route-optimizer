import { DollarSign, Fuel, Leaf } from "lucide-react";
import type { RouteAlternative } from "@/types";

interface CostAnalysisProps {
  routes: RouteAlternative[];
}

export function CostAnalysis({ routes }: CostAnalysisProps) {
  const worstFuel = Math.max(...routes.map((r) => r.metrics.fuel_cost_usd));

  return (
    <div className="p-4">
      <h2 className="text-sm font-semibold text-slate-300 mb-3 flex items-center gap-2">
        <DollarSign className="w-4 h-4 text-teal-400" />
        Cost Analysis
      </h2>
      <div className="space-y-3">
        {routes.map((route) => (
          <div
            key={route.route_id}
            className="flex items-center justify-between p-2.5 rounded-lg bg-slate-900/80 border border-slate-700"
          >
            <div className="flex items-center gap-2">
              <div
                className="w-2 h-2 rounded-full"
                style={{ backgroundColor: route.color }}
              ></div>
              <span className="text-xs text-slate-300">{route.name}</span>
            </div>
            <div className="text-right">
              <div className="text-sm font-bold" style={{ color: route.color }}>
                ${route.metrics.fuel_cost_usd.toFixed(2)}
              </div>
              <div className="text-[10px] text-slate-500">
                {route.metrics.fuel_liters} L fuel
              </div>
            </div>
          </div>
        ))}
      </div>

      <div className="mt-3 p-2.5 rounded-lg bg-emerald-500/10 border border-emerald-500/20">
        <div className="flex items-center gap-2 mb-1">
          <Leaf className="w-3.5 h-3.5 text-emerald-400" />
          <span className="text-xs text-emerald-300 font-medium">
            Environmental Impact
          </span>
        </div>
        <div className="space-y-1">
          {routes.map((route) => (
            <div
              key={route.route_id}
              className="flex items-center justify-between text-xs"
            >
              <span className="text-slate-400">{route.name}</span>
              <span className="text-slate-300">
                {route.metrics.co2_emissions_kg} kg CO₂
              </span>
            </div>
          ))}
        </div>
      </div>

      {routes.some((r) => r.is_recommended) && (
        <div className="mt-3 p-2.5 rounded-lg bg-emerald-500/10 border border-emerald-500/20 text-center">
          <Fuel className="w-3.5 h-3.5 text-emerald-400 mx-auto mb-1" />
          <div className="text-xs text-emerald-300">
            <strong>
              {routes.find((r) => r.is_recommended)?.name} saves $
              {(
                worstFuel -
                (routes.find((r) => r.is_recommended)?.metrics.fuel_cost_usd ||
                  0)
              ).toFixed(2)}
            </strong>{" "}
            in fuel costs vs congested path
          </div>
        </div>
      )}
    </div>
  );
}
