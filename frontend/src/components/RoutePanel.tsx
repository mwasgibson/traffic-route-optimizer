import { useState, useCallback, useRef, useEffect } from "react";
import {
  MapPin,
  Navigation,
  Gauge,
  Shield,
  Fuel,
  AlertTriangle,
  CheckCircle,
  Info,
  Wind,
  Droplets,
  Eye,
  Thermometer,
  Search,
  X,
  Loader2,
  Car,
  Bike,
  Truck,
  Bus,
  LocateFixed,
  Crosshair,
  MapPinned,
  Plus,
  Trash2,
  Footprints,
  PersonStanding,
} from "lucide-react";
import { routeApi } from "@/services/api";
import { useGeolocation } from "@/hooks/useGeolocation";
import type {
  RouteOptimizationResponse,
  RouteAlternative,
  WeatherCondition,
  Coordinates,
  LocationSearchResult,
} from "@/types";

interface RoutePanelProps {
  data: RouteOptimizationResponse | null;
  activeRouteId: string | null;
  onRouteSelect: (routeId: string | null) => void;
  onOptimize: (params: {
    origin: Coordinates;
    destination: Coordinates;
    waypoints: Coordinates[];
    transportMode: "driving" | "cycling" | "walking";
    timeWeight: number;
    distanceWeight: number;
    safetyWeight: number;
    fuelWeight: number;
    vehicleType: string;
    avoidTolls: boolean;
    avoidHighways: boolean;
  }) => void;
  loading: boolean;
}

/* ─── Location Search Input ─────────────────────────────── */
function LocationSearchInput({
  label,
  value,
  onSelect,
  iconColor,
  showLocateButton,
  onLocate,
  locating,
}: {
  label: string;
  value: string;
  onSelect: (name: string, coords: Coordinates) => void;
  iconColor: string;
  showLocateButton?: boolean;
  onLocate?: () => void;
  locating?: boolean;
}) {
  const [query, setQuery] = useState(value);
  const [results, setResults] = useState<LocationSearchResult[]>([]);
  const [searching, setSearching] = useState(false);
  const [open, setOpen] = useState(false);
  const wrapperRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    setQuery(value);
  }, [value]);

  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (
        wrapperRef.current &&
        !wrapperRef.current.contains(e.target as Node)
      ) {
        setOpen(false);
      }
    };
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  const doSearch = useCallback(async (q: string) => {
    if (q.length < 2) {
      setResults([]);
      return;
    }
    setSearching(true);
    try {
      const res = await routeApi.searchLocations(q, 8);
      setResults(res);
    } catch (err) {
      setResults([]);
    } finally {
      setSearching(false);
    }
  }, []);

  useEffect(() => {
    const timer = setTimeout(() => doSearch(query), 400);
    return () => clearTimeout(timer);
  }, [query, doSearch]);

  const handleSelect = (r: LocationSearchResult) => {
    setQuery(r.name);
    onSelect(r.name, r.coordinates);
    setOpen(false);
    setResults([]);
  };

  return (
    <div ref={wrapperRef} className="relative">
      <div className="flex items-center justify-between mb-1">
        <label className="text-xs text-slate-400 flex items-center gap-1">
          <MapPinned className="w-3 h-3" />
          {label}
        </label>
        {showLocateButton && onLocate && (
          <button
            onClick={onLocate}
            disabled={locating}
            className="flex items-center gap-1 text-[10px] text-blue-400 hover:text-blue-300 transition-colors disabled:text-slate-600"
            title="Use my current GPS location"
          >
            {locating ? (
              <Loader2 className="w-3 h-3 animate-spin" />
            ) : (
              <Crosshair className="w-3 h-3" />
            )}
            {locating ? "Locating..." : "Use my location"}
          </button>
        )}
      </div>
      <div className="relative">
        <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-500" />
        <input
          type="text"
          value={query}
          onChange={(e) => {
            setQuery(e.target.value);
            setOpen(true);
          }}
          onFocus={() => query.length >= 2 && setOpen(true)}
          placeholder={`Search ${label.toLowerCase()} (e.g. "Nairobi Central", "Jomo Kenyatta Airport")...`}
          className="w-full bg-slate-900 border border-slate-600 rounded-lg pl-9 pr-8 py-2 text-sm text-white placeholder-slate-500 focus:outline-none focus:border-blue-500 transition-colors"
        />
        <div
          className={`absolute right-2 top-1/2 -translate-y-1/2 w-2 h-2 rounded-full ${iconColor}`}
        />
        {query && (
          <button
            onClick={() => {
              setQuery("");
              onSelect("", { lat: Number.NaN, lon: Number.NaN });
            }}
            className="absolute right-6 top-1/2 -translate-y-1/2 text-slate-500 hover:text-white"
          >
            <X className="w-3.5 h-3.5" />
          </button>
        )}
      </div>

      {open && (searching || results.length > 0) && (
        <div className="absolute z-50 w-full mt-1 bg-slate-800 border border-slate-600 rounded-lg shadow-xl overflow-hidden max-h-64 overflow-y-auto">
          {searching && (
            <div className="flex items-center gap-2 px-3 py-2.5 text-xs text-slate-400">
              <Loader2 className="w-3.5 h-3.5 animate-spin" />
              Searching OpenStreetMap...
            </div>
          )}
          {results.map((r) => (
            <button
              key={r.place_id}
              onClick={() => handleSelect(r)}
              className="w-full text-left px-3 py-2.5 hover:bg-slate-700 transition-colors border-b border-slate-700/50 last:border-0"
            >
              <div className="text-sm text-white font-medium">{r.name}</div>
              <div className="text-xs text-slate-400 leading-snug">
                {r.address}
              </div>
              <div className="flex items-center gap-2 mt-1">
                <span className="text-[10px] px-1.5 py-0.5 rounded bg-slate-700 text-slate-400 capitalize">
                  {r.type}
                </span>
                <span className="text-[10px] text-slate-500 font-mono">
                  {r.coordinates.lat.toFixed(5)}, {r.coordinates.lon.toFixed(5)}
                </span>
              </div>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

/* ─── Weather Card ──────────────────────────────────────── */
function WeatherCard({ weather }: { weather: WeatherCondition }) {
  return (
    <div className="p-4 border-b border-slate-700">
      <h2 className="text-sm font-semibold text-slate-300 mb-3 flex items-center gap-2">
        <Wind className="w-4 h-4 text-sky-400" />
        Weather Conditions
      </h2>
      <div className="grid grid-cols-2 gap-2">
        <div className="bg-slate-900/80 rounded-lg p-3 border border-slate-700">
          <div className="text-xs text-slate-400 mb-1 flex items-center gap-1">
            <Thermometer className="w-3 h-3" /> Temperature
          </div>
          <div className="text-lg font-bold text-white">
            {weather.temperature}°C
          </div>
        </div>
        <div className="bg-slate-900/80 rounded-lg p-3 border border-slate-700">
          <div className="text-xs text-slate-400 mb-1 flex items-center gap-1">
            <Eye className="w-3 h-3" /> Visibility
          </div>
          <div className="text-lg font-bold text-white">
            {weather.visibility} km
          </div>
        </div>
        <div className="bg-slate-900/80 rounded-lg p-3 border border-slate-700">
          <div className="text-xs text-slate-400 mb-1 flex items-center gap-1">
            <Droplets className="w-3 h-3" /> Rainfall
          </div>
          <div className="text-lg font-bold text-white">
            {weather.rainfall} mm
          </div>
        </div>
        <div className="bg-slate-900/80 rounded-lg p-3 border border-slate-700">
          <div className="text-xs text-slate-400 mb-1 flex items-center gap-1">
            <Wind className="w-3 h-3" /> Wind
          </div>
          <div className="text-lg font-bold text-white">
            {weather.wind_speed} km/h
          </div>
        </div>
      </div>
      <div className="mt-3 p-2.5 rounded-lg bg-emerald-500/10 border border-emerald-500/20">
        <div className="flex items-center gap-2">
          <CheckCircle className="w-4 h-4 text-emerald-400 shrink-0" />
          <span className="text-xs text-emerald-300 font-medium">
            Impact:{" "}
            {weather.impact_score < 3
              ? "Low"
              : weather.impact_score < 6
                ? "Medium"
                : "High"}
            {" — "}
            {weather.impact_score < 3
              ? "Favorable for travel"
              : "Exercise caution"}
          </span>
        </div>
      </div>
    </div>
  );
}

/* ─── Route Card ────────────────────────────────────────── */
function RouteCard({
  route,
  isActive,
  onClick,
}: {
  route: RouteAlternative;
  isActive: boolean;
  onClick: () => void;
}) {
  const [expanded, setExpanded] = useState(false);

  const getTrafficBadge = (condition: string) => {
    const styles: Record<string, string> = {
      light: "bg-emerald-500/15 text-emerald-400",
      moderate: "bg-amber-500/15 text-amber-400",
      heavy: "bg-red-500/15 text-red-400",
      severe: "bg-red-600/15 text-red-500",
    };
    return styles[condition] || styles.light;
  };

  return (
    <div
      className="p-4 border-b border-slate-700/50 cursor-pointer transition-all hover:bg-slate-700/30"
      style={{
        borderLeftWidth: isActive ? "4px" : "0px",
        borderLeftColor: isActive ? route.color : "transparent",
        backgroundColor: isActive ? "rgba(51,65,85,0.2)" : undefined,
      }}
      onClick={onClick}
    >
      <div className="flex items-center justify-between mb-2">
        <div className="flex items-center gap-2">
          <div
            className="w-3 h-3 rounded-full"
            style={{ backgroundColor: route.color }}
          />
          <span className="font-semibold text-white text-sm">{route.name}</span>
          {route.is_recommended && (
            <span className="px-2 py-0.5 rounded-lg bg-emerald-500/20 text-emerald-400 text-[10px] font-bold border border-emerald-500/30">
              RECOMMENDED
            </span>
          )}
        </div>
        <span className="text-lg font-bold" style={{ color: route.color }}>
          {route.metrics.overall_score}
        </span>
      </div>

      <div className="text-xs text-slate-500 mb-3">{route.description}</div>

      <div className="grid grid-cols-3 gap-2 mb-3">
        <div className="text-center">
          <div className="text-xs text-slate-400">Distance</div>
          <div className="text-sm font-bold text-white">
            {route.metrics.distance_km} km
          </div>
        </div>
        <div className="text-center">
          <div className="text-xs text-slate-400">Time</div>
          <div className="text-sm font-bold text-white">
            {route.metrics.estimated_time_min} min
          </div>
        </div>
        <div className="text-center">
          <div className="text-xs text-slate-400">Traffic</div>
          <span
            className={`inline-block px-2 py-0.5 rounded-full text-[10px] font-medium ${getTrafficBadge(route.metrics.traffic_condition)}`}
          >
            {route.metrics.traffic_condition}
          </span>
        </div>
      </div>

      <div className="w-full h-1.5 bg-slate-700 rounded-full overflow-hidden mb-2">
        <div
          className="h-full rounded-full transition-all duration-500"
          style={{
            width: `${route.metrics.overall_score}%`,
            backgroundColor: route.color,
          }}
        />
      </div>

      <button
        onClick={(e) => {
          e.stopPropagation();
          setExpanded(!expanded);
        }}
        className="text-xs text-slate-400 hover:text-white transition-colors flex items-center gap-1"
      >
        <Info className="w-3 h-3" />
        {expanded ? "Hide details" : "Show details"}
      </button>

      {expanded && (
        <div className="mt-3 space-y-2">
          <div className="grid grid-cols-2 gap-2 text-xs">
            <div className="flex items-center gap-1.5 text-slate-300">
              <Shield className="w-3.5 h-3.5 text-emerald-400" />
              Safety:{" "}
              <span className="font-bold">{route.metrics.safety_score}/10</span>
            </div>
            <div className="flex items-center gap-1.5 text-slate-300">
              <Fuel className="w-3.5 h-3.5 text-amber-400" />
              Fuel:{" "}
              <span className="font-bold">{route.metrics.fuel_liters} L</span>
            </div>
            <div className="flex items-center gap-1.5 text-slate-300">
              <Gauge className="w-3.5 h-3.5 text-blue-400" />
              Cost:{" "}
              <span className="font-bold">${route.metrics.fuel_cost_usd}</span>
            </div>
            <div className="flex items-center gap-1.5 text-slate-300">
              <Navigation className="w-3.5 h-3.5 text-purple-400" />
              CO2:{" "}
              <span className="font-bold">
                {route.metrics.co2_emissions_kg} kg
              </span>
            </div>
          </div>
          {route.warnings.length > 0 && (
            <div className="space-y-1">
              {route.warnings.map((w, i) => (
                <div
                  key={i}
                  className="flex items-start gap-1.5 p-2 rounded bg-red-500/10 border border-red-500/20"
                >
                  <AlertTriangle className="w-3.5 h-3.5 text-red-400 shrink-0 mt-0.5" />
                  <span className="text-xs text-red-300">{w}</span>
                </div>
              ))}
            </div>
          )}
          {route.insights.length > 0 && (
            <div className="space-y-1">
              {route.insights.map((insight, i) => (
                <div
                  key={i}
                  className="flex items-start gap-1.5 p-2 rounded bg-blue-500/10 border border-blue-500/20"
                >
                  <CheckCircle className="w-3.5 h-3.5 text-blue-400 shrink-0 mt-0.5" />
                  <span className="text-xs text-blue-300">{insight}</span>
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

/* ─── Vehicle Selector ──────────────────────────────────── */
function VehicleSelector({
  value,
  onChange,
}: {
  value: string;
  onChange: (v: string) => void;
}) {
  const vehicles = [
    { id: "car", icon: Car, label: "Car" },
    { id: "motorcycle", icon: Bike, label: "Bike" },
    { id: "truck", icon: Truck, label: "Truck" },
    { id: "bus", icon: Bus, label: "Bus" },
    { id: "footprint", icon: Footprints, label: "Footprint" },
  ];

  return (
    <div className="grid grid-cols-4 gap-2">
      {vehicles.map((v) => {
        const Icon = v.icon;
        const active = value === v.id;
        return (
          <button
            key={v.id}
            onClick={() => onChange(v.id)}
            className={`flex flex-col items-center gap-1 p-2 rounded-lg border transition-all text-xs ${
              active
                ? "bg-blue-500/20 border-blue-500/40 text-blue-400"
                : "bg-slate-900/50 border-slate-700 text-slate-400 hover:text-slate-300"
            }`}
          >
            <Icon className="w-4 h-4" />
            <span>{v.label}</span>
          </button>
        );
      })}
    </div>
  );
}

/* ─── Geolocation Error Banner ──────────────────────────── */
function GeoErrorBanner({
  error,
  onRetry,
  onDismiss,
}: {
  error: string;
  onRetry: () => void;
  onDismiss: () => void;
}) {
  return (
    <div className="mx-4 mb-3 p-3 rounded-lg bg-amber-500/10 border border-amber-500/20">
      <div className="flex items-start gap-2">
        <LocateFixed className="w-4 h-4 text-amber-400 shrink-0 mt-0.5" />
        <div className="flex-1">
          <p className="text-xs text-amber-200 leading-relaxed">{error}</p>
          <div className="flex gap-2 mt-2">
            <button
              onClick={onRetry}
              className="text-[10px] px-2 py-1 rounded bg-amber-500/20 text-amber-300 hover:bg-amber-500/30 transition-colors"
            >
              Try Again
            </button>
            <button
              onClick={onDismiss}
              className="text-[10px] px-2 py-1 rounded bg-slate-700 text-slate-400 hover:bg-slate-600 transition-colors"
            >
              Dismiss
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

/* ─── Main Panel ────────────────────────────────────────── */
export function RoutePanel({
  data,
  activeRouteId,
  onRouteSelect,
  onOptimize,
  loading,
}: RoutePanelProps) {
  const [originName, setOriginName] = useState("");
  const [originCoords, setOriginCoords] = useState<Coordinates | null>(null);
  const [destName, setDestName] = useState("");
  const [destCoords, setDestCoords] = useState<Coordinates | null>(null);

  const [timeWeight, setTimeWeight] = useState(85);
  const [distanceWeight, setDistanceWeight] = useState(60);
  const [safetyWeight, setSafetyWeight] = useState(90);
  const [fuelWeight, setFuelWeight] = useState(75);
  const [vehicleType, setVehicleType] = useState("car");
  const [avoidTolls, setAvoidTolls] = useState(false);
  const [avoidHighways, setAvoidHighways] = useState(false);

  const geo = useGeolocation();

  const canOptimize = originCoords !== null && destCoords !== null;

  const [stops, setStops] = useState<
    Array<{ name: string; coords: Coordinates }>
  >([]);
  const [transportMode, setTransportMode] = useState<
    "driving" | "cycling" | "walking"
  >("driving");

  const handleOptimize = () => {
    if (!canOptimize) return;
    onOptimize({
      origin: originCoords!,
      destination: destCoords!,
      waypoints: stops.map((s) => s.coords),
      transportMode,
      timeWeight,
      distanceWeight,
      safetyWeight,
      fuelWeight,
      vehicleType,
      avoidTolls,
      avoidHighways,
    });
  };

  // Auto-fill origin when geolocation succeeds
  useEffect(() => {
    if (geo.coords && !originCoords) {
      setOriginCoords(geo.coords);
      setOriginName(
        geo.address ||
          `My Location (${geo.coords.lat.toFixed(5)}, ${geo.coords.lon.toFixed(5)})`,
      );
    }
  }, [geo.coords, geo.address, originCoords]);

  return (
    <div className="w-80 bg-slate-800/50 border-r border-slate-700 flex flex-col overflow-y-auto h-full">
      {/* Route Input */}
      <div className="p-4 border-b border-slate-700">
        <h2 className="text-sm font-semibold text-slate-300 mb-3 flex items-center gap-2">
          <MapPin className="w-4 h-4 text-blue-400" />
          Route Configuration
        </h2>

        {geo.error && (
          <GeoErrorBanner
            error={geo.error}
            onRetry={geo.requestLocation}
            onDismiss={geo.clearError}
          />
        )}

        <div className="space-y-3">
          <LocationSearchInput
            label="Origin"
            value={originName}
            onSelect={(name, coords) => {
              setOriginName(name);
              setOriginCoords(
                name && Number.isFinite(coords.lat) && Number.isFinite(coords.lon)
                  ? coords
                  : null,
              );
            }}
            iconColor="bg-emerald-400"
            showLocateButton={true}
            onLocate={geo.requestLocation}
            locating={geo.loading}
          />
          <div className="flex justify-center">
            <Navigation className="w-4 h-4 text-slate-500 rotate-180" />
          </div>
          <LocationSearchInput
            label="Destination"
            value={destName}
            onSelect={(name, coords) => {
              setDestName(name);
              setDestCoords(
                name && Number.isFinite(coords.lat) && Number.isFinite(coords.lon)
                  ? coords
                  : null,
              );
            }}
            iconColor="bg-red-400"
          />
        </div>

        {/* Multi-stop waypoints */}
        <div className="mt-3 space-y-2">
          {stops.map((stop, idx) => (
            <div key={idx} className="flex items-center gap-2">
              <div className="flex-1">
                <LocationSearchInput
                  label={`Stop ${idx + 1}`}
                  value={stop.name}
                  onSelect={(name, coords) => {
                    const next = [...stops];
                    next[idx] = { name, coords };
                    setStops(next);
                  }}
                  iconColor="bg-amber-400"
                />
              </div>
              <button
                onClick={() => setStops(stops.filter((_, i) => i !== idx))}
                className="mt-4 p-1.5 rounded-lg bg-slate-900 border border-slate-700 text-slate-500 hover:text-red-400 hover:border-red-500/40"
                title="Remove stop"
              >
                <Trash2 className="w-3.5 h-3.5" />
              </button>
            </div>
          ))}
          {stops.length < 8 && (
            <button
              onClick={() =>
                setStops([...stops, { name: "", coords: { lat: 0, lon: 0 } }])
              }
              className="flex items-center gap-1.5 text-xs text-blue-400 hover:text-blue-300 transition-colors"
            >
              <Plus className="w-3.5 h-3.5" />
              Add stop (multi-stop route)
            </button>
          )}
        </div>

        <div className="mt-4">
          <label className="text-xs text-slate-400 mb-2 block">
            Transport Mode
          </label>
          <ModeSelector value={transportMode} onChange={setTransportMode} />
        </div>

        <div className="mt-4">
          <label className="text-xs text-slate-400 mb-2 block">
            Vehicle Type
          </label>
          <VehicleSelector value={vehicleType} onChange={setVehicleType} />
        </div>

        <div className="mt-3 flex gap-3">
          <label className="flex items-center gap-2 text-xs text-slate-300 cursor-pointer">
            <input
              type="checkbox"
              checked={avoidTolls}
              onChange={(e) => setAvoidTolls(e.target.checked)}
              className="rounded border-slate-600 bg-slate-900 text-blue-500 focus:ring-blue-500"
            />
            Avoid tolls
          </label>
          <label className="flex items-center gap-2 text-xs text-slate-300 cursor-pointer">
            <input
              type="checkbox"
              checked={avoidHighways}
              onChange={(e) => setAvoidHighways(e.target.checked)}
              className="rounded border-slate-600 bg-slate-900 text-blue-500 focus:ring-blue-500"
            />
            Avoid highways
          </label>
        </div>
      </div>

      {/* Weights */}
      <div className="p-4 border-b border-slate-700">
        <h2 className="text-sm font-semibold text-slate-300 mb-3 flex items-center gap-2">
          <Gauge className="w-4 h-4 text-amber-400" />
          Optimization Weights
        </h2>
        <div className="space-y-3">
          {[
            {
              label: "Travel Time",
              value: timeWeight,
              set: setTimeWeight,
              color: "bg-blue-500",
              text: "text-blue-400",
            },
            {
              label: "Distance",
              value: distanceWeight,
              set: setDistanceWeight,
              color: "bg-purple-500",
              text: "text-purple-400",
            },
            {
              label: "Safety Score",
              value: safetyWeight,
              set: setSafetyWeight,
              color: "bg-emerald-500",
              text: "text-emerald-400",
            },
            {
              label: "Fuel Efficiency",
              value: fuelWeight,
              set: setFuelWeight,
              color: "bg-amber-500",
              text: "text-amber-400",
            },
          ].map((s) => (
            <div key={s.label}>
              <div className="flex justify-between text-xs mb-1">
                <span className="text-slate-400">{s.label}</span>
                <span className={`font-medium ${s.text}`}>{s.value}%</span>
              </div>
              <input
                type="range"
                min="0"
                max="100"
                value={s.value}
                onChange={(e) => s.set(parseInt(e.target.value))}
                className="w-full"
              />
            </div>
          ))}
        </div>
      </div>

      {/* Optimize Button */}
      <div className="p-4">
        <button
          onClick={handleOptimize}
          disabled={!canOptimize || loading}
          className={`w-full font-semibold py-2.5 rounded-lg transition-all flex items-center justify-center gap-2 shadow-lg active:scale-[0.98] disabled:cursor-not-allowed ${
            canOptimize && !loading
              ? "bg-blue-600 hover:bg-blue-500 text-white shadow-blue-600/20"
              : "bg-slate-700 text-slate-500"
          }`}
        >
          {loading ? (
            <>
              <Loader2 className="w-4 h-4 animate-spin" />
              Optimizing...
            </>
          ) : (
            <>
              <Navigation className="w-4 h-4" />
              {canOptimize ? "Optimize Routes" : "Select locations first"}
            </>
          )}
        </button>
      </div>

      {/* Results */}
      {data && (
        <>
          <WeatherCard weather={data.weather} />
          <div className="flex-1">
            <div className="p-3 text-xs font-semibold text-slate-400 uppercase tracking-wider">
              Route Alternatives
            </div>
            {data.routes.map((route) => (
              <RouteCard
                key={route.route_id}
                route={route}
                isActive={activeRouteId === route.route_id}
                onClick={() =>
                  onRouteSelect(
                    activeRouteId === route.route_id ? null : route.route_id,
                  )
                }
              />
            ))}
          </div>
          <div className="p-4 border-t border-slate-700 bg-slate-800/80">
            <div className="text-xs text-slate-400 mb-2">
              Optimization Summary
            </div>
            <div className="grid grid-cols-2 gap-2 text-xs">
              <div className="p-2 rounded-lg bg-emerald-500/10 border border-emerald-500/20">
                <div className="text-emerald-400 font-bold">
                  {data.time_saved_vs_worst_min} min
                </div>
                <div className="text-slate-500">Time Saved</div>
              </div>
              <div className="p-2 rounded-lg bg-emerald-500/10 border border-emerald-500/20">
                <div className="text-emerald-400 font-bold">
                  ${data.fuel_saved_vs_worst_usd}
                </div>
                <div className="text-slate-500">Fuel Saved</div>
              </div>
            </div>
            <div className="mt-2 text-[10px] text-slate-500 text-center">
              Processed in {data.processing_time_ms}ms ·{" "}
              {data.data_sources.length} sources
            </div>
          </div>
        </>
      )}
    </div>
  );
}

/* ─── Transport Mode Selector ───────────────────────────── */
function ModeSelector({
  value,
  onChange,
}: {
  value: string;
  onChange: (v: "driving" | "cycling" | "walking") => void;
}) {
  const modes = [
    { id: "driving", icon: Car, label: "Driving" },
    { id: "cycling", icon: Bike, label: "Cycling" },
    { id: "walking", icon: PersonStanding, label: "Walking" },
  ];
  return (
    <div className="grid grid-cols-3 gap-2">
      {modes.map((m) => {
        const Icon = m.icon;
        const active = value === m.id;
        return (
          <button
            key={m.id}
            onClick={() => onChange(m.id as "driving" | "cycling" | "walking")}
            className={`flex flex-col items-center gap-1 p-2 rounded-lg border transition-all text-xs ${
              active
                ? "bg-purple-500/20 border-purple-500/40 text-purple-300"
                : "bg-slate-900/50 border-slate-700 text-slate-400 hover:text-slate-300"
            }`}
          >
            <Icon className="w-4 h-4" />
            <span>{m.label}</span>
          </button>
        );
      })}
    </div>
  );
}
