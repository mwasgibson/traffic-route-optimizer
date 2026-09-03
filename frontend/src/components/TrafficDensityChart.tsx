import { useMemo } from "react";
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  Cell,
} from "recharts";
import { TrendingUp } from "lucide-react";

interface TrafficDensityChartProps {
  data?: { hour: string; density: number; label: string }[];
}

export function TrafficDensityChart({ data }: TrafficDensityChartProps) {
  const defaultData = useMemo(
    () => [
      { hour: "06:00", density: 25, label: "Low" },
      { hour: "08:00", density: 35, label: "Low" },
      { hour: "10:00", density: 65, label: "Moderate" },
      { hour: "12:00", density: 90, label: "Heavy" },
      { hour: "14:00", density: 70, label: "Moderate" },
      { hour: "16:00", density: 45, label: "Moderate" },
      { hour: "18:00", density: 85, label: "Heavy" },
    ],
    [],
  );

  const chartData = data || defaultData;

  const getBarColor = (density: number) => {
    if (density < 40) return "#10b981";
    if (density < 70) return "#f59e0b";
    return "#ef4444";
  };

  return (
    <div className="p-4 border-b border-slate-700">
      <h2 className="text-sm font-semibold text-slate-300 mb-3 flex items-center gap-2">
        <TrendingUp className="w-4 h-4 text-rose-400" />
        Traffic Density Forecast
      </h2>
      <div className="h-28">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart
            data={chartData}
            margin={{ top: 5, right: 5, left: -20, bottom: 0 }}
          >
            <XAxis dataKey="hour" tick={{ fill: "#64748b", fontSize: 10 }} />
            <YAxis tick={{ fill: "#64748b", fontSize: 10 }} />
            <Tooltip
              contentStyle={{
                backgroundColor: "#1e293b",
                border: "1px solid #475569",
                borderRadius: "8px",
              }}
              itemStyle={{ color: "#e2e8f0" }}
              formatter={(value: number) => [`${value}%`, "Congestion"]}
            />
            <Bar dataKey="density" radius={[4, 4, 0, 0]} fill="#3b82f6">
              {chartData.map((entry, index) => (
                <Cell key={`cell-${index}`} fill={getBarColor(entry.density)} />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>
      <div className="flex justify-between mt-2 text-[10px] text-slate-500">
        <span>Low</span>
        <span>Moderate</span>
        <span>Heavy</span>
      </div>
    </div>
  );
}
