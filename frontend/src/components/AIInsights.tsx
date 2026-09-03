import { Lightbulb, AlertTriangle, CheckCircle, Info } from "lucide-react";
import type { RouteAlternative } from "@/types";

interface AIInsightsProps {
  routes: RouteAlternative[];
  recommendedRouteId: string;
}

export function AIInsights({ routes, recommendedRouteId }: AIInsightsProps) {
  const recommended = routes.find((r) => r.route_id === recommendedRouteId);
  const worst = routes.reduce((prev, curr) =>
    prev.metrics.overall_score < curr.metrics.overall_score ? prev : curr,
  );

  const allInsights: { type: "success" | "info" | "warning"; text: string }[] =
    [];

  if (recommended) {
    const timeSaved =
      worst.metrics.estimated_time_min - recommended.metrics.estimated_time_min;
    const fuelSaved =
      worst.metrics.fuel_cost_usd - recommended.metrics.fuel_cost_usd;

    if (timeSaved > 0) {
      allInsights.push({
        type: "success",
        text: `Route ${recommended.name} saves ${timeSaved.toFixed(0)} minutes compared to the congested path despite being ${(recommended.metrics.distance_km - Math.min(...routes.map((r) => r.metrics.distance_km))).toFixed(1)} km lngger.`,
      });
    }

    if (fuelSaved > 0) {
      allInsights.push({
        type: "success",
        text: `More fuel-efficient, saving $${fuelSaved.toFixed(2)} vs the worst route.`,
      });
    }

    recommended.insights.forEach((insight) => {
      allInsights.push({ type: "info", text: insight });
    });

    recommended.warnings.forEach((warning) => {
      allInsights.push({ type: "warning", text: warning });
    });
  }

  const getIcon = (type: string) => {
    switch (type) {
      case "success":
        return (
          <CheckCircle className="w-4 h-4 text-emerald-400 shrink-0 mt-0.5" />
        );
      case "warning":
        return (
          <AlertTriangle className="w-4 h-4 text-amber-400 shrink-0 mt-0.5" />
        );
      default:
        return <Info className="w-4 h-4 text-blue-400 shrink-0 mt-0.5" />;
    }
  };

  const getBg = (type: string) => {
    switch (type) {
      case "success":
        return "bg-emerald-500/10 border-emerald-500/20";
      case "warning":
        return "bg-amber-500/10 border-amber-500/20";
      default:
        return "bg-blue-500/10 border-blue-500/20";
    }
  };

  const getText = (type: string) => {
    switch (type) {
      case "success":
        return "text-emerald-200";
      case "warning":
        return "text-amber-200";
      default:
        return "text-blue-200";
    }
  };

  return (
    <div className="p-4">
      <h2 className="text-sm font-semibold text-slate-300 mb-3 flex items-center gap-2">
        <Lightbulb className="w-4 h-4 text-violet-400" />
        AI Insights
      </h2>
      <div className="space-y-2.5">
        {allInsights.map((insight, i) => (
          <div
            key={i}
            className={`flex items-start gap-2 p-2.5 rounded-lg border ${getBg(insight.type)}`}
          >
            {getIcon(insight.type)}
            <p className={`text-xs leading-relaxed ${getText(insight.type)}`}>
              {insight.text}
            </p>
          </div>
        ))}
      </div>
    </div>
  );
}
