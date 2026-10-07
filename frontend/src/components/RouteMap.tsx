import { useEffect, useRef } from "react";
import L from "leaflet";
// @ts-ignore
import "leaflet/dist/leaflet.css";
import type { RouteAlternative, Coordinates } from "@/types";

interface RouteMapProps {
  routes: RouteAlternative[];
  origin: Coordinates;
  destination: Coordinates;
  activeRouteId: string | null;
  waypoints?: Coordinates[];
}

export function RouteMap({
  routes,
  origin,
  destination,
  activeRouteId,
  waypoints = [],
}: RouteMapProps) {
  const mapRef = useRef<HTMLDivElement>(null);
  const leafletMap = useRef<L.Map | null>(null);
  const layersRef = useRef<{
    routes: L.LayerGroup;
    markers: L.LayerGroup;
    heatmap: L.LayerGroup;
  } | null>(null);

  // Initialize map
  useEffect(() => {
    if (!mapRef.current || leafletMap.current) return;

    const map = L.map(mapRef.current, {
      zoomControl: false,
      attributionControl: false,
    });

    L.tileLayer(
      "https://{s}.basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}{r}.png",
      {
        maxZoom: 19,
      },
    ).addTo(map);

    L.control.zoom({ position: "topright" }).addTo(map);

    leafletMap.current = map;
    layersRef.current = {
      routes: L.layerGroup().addTo(map),
      markers: L.layerGroup().addTo(map),
      heatmap: L.layerGroup().addTo(map),
    };

    // Ensure map resizes correctly if container size changes
    const resizeObserver = new ResizeObserver(() => {
      map.invalidateSize();
    });
    resizeObserver.observe(mapRef.current);

    return () => {
      resizeObserver.disconnect();
      map.remove();
      leafletMap.current = null;
      layersRef.current = null;
    };
  }, []);

  // Update origin/destination markers
  useEffect(() => {
    if (!leafletMap.current || !layersRef.current) return;
    const { markers } = layersRef.current;
    markers.clearLayers();

    const createIcon = (color: string) =>
      L.divIcon({
        className: "custom-marker",
        html: `<div style="width:16px;height:16px;background:${color};border-radius:50%;border:2px solid white;box-shadow:0 0 8px ${color}80;"></div>`,
        iconSize: [16, 16],
        iconAnchor: [8, 8],
      });

    L.marker([origin.lat, origin.lon], { icon: createIcon("#10b981") })
      .addTo(markers)
      .bindPopup('<b style="color:#333">Origin</b>');

    L.marker([destination.lat, destination.lon], {
      icon: createIcon("#ef4444"),
    })
      .addTo(markers)
      .bindPopup('<b style="color:#333">Destination</b>');

    (waypoints ?? []).forEach((w, i) => {
      L.marker([w.lat, w.lon], { icon: createIcon("#f59e0b") })
        .addTo(markers)
        .bindPopup(`<b style="color:#333">Stop ${i + 1}</b>`);
    });
  }, [origin, destination, waypoints]);

  // Update routes
  useEffect(() => {
    if (!leafletMap.current || !layersRef.current) return;
    const { routes: routeLayer } = layersRef.current;
    routeLayer.clearLayers();

    routes.forEach((route) => {
      const isActive =
        activeRouteId === null || activeRouteId === route.route_id;
      const isRecommended = route.is_recommended;

      // Fixed: type name is LatLngExpression and uses lon instead of lon
      const latlngs = route.path.map(
        (p) => [p.lat, p.lon] as L.LatLngExpression,
      );

      if (isRecommended && isActive) {
        L.polyline(latlngs, {
          color: route.color,
          weight: 12,
          opacity: 0.12,
          lineCap: "round",
        }).addTo(routeLayer);
      }

      L.polyline(latlngs, {
        color: route.color,
        weight: isActive ? (isRecommended ? 5 : 3) : 2,
        opacity: isActive ? (isRecommended ? 0.9 : 0.6) : 0.15,
        dashArray: route.route_id === "route_c" ? "8, 6" : undefined,
        lineCap: "round",
        lineJoin: "round",
      }).addTo(routeLayer);

      // Incident markers
      route.traffic_segments.forEach((seg) => {
        if (seg.incident_count > 0 || seg.congestion_level === "severe") {
          const midLat = (seg.start_coords.lat + seg.end_coords.lat) / 2;
          const midLon = (seg.start_coords.lon + seg.end_coords.lon) / 2;

          L.circleMarker([midLat, midLon], {
            radius: 6,
            fillColor: "#ef4444",
            color: "#fff",
            weight: 1,
            opacity: 1,
            fillOpacity: 0.8,
          })
            .addTo(routeLayer)
            .bindPopup(
              `<b style="color:#333">Incident</b><br/>` +
                `Congestion: ${seg.congestion_level}<br/>` +
                `Delay: ${seg.delay_minutes} min`,
            );
        }
      });
    });

    // Fit bounds
    const allPoints = routes.flatMap((r) => r.path);
    if (allPoints.length > 0) {
      const bounds = L.latLngBounds(allPoints.map((p) => [p.lat, p.lon]));
      leafletMap.current.fitBounds(bounds, { padding: [60, 60], maxZoom: 15 });
    }
  }, [routes, activeRouteId]);

  return (
    <div className="relative w-full h-full">
      <div ref={mapRef} className="w-full h-full" />
      {/* Legend */}
      <div className="absolute bottom-4 left-4 bg-slate-800/90 backdrop-blur-sm border border-slate-600 rounded-lg p-3 z-[400]">
        <div className="text-xs font-semibold text-slate-300 mb-2">
          Route Legend
        </div>
        <div className="space-y-1.5">
          <div className="flex items-center gap-2">
            <div className="w-6 h-1 rounded bg-emerald-500"></div>
            <span className="text-xs text-slate-400">
              Optimal (AI Recommended)
            </span>
          </div>
          <div className="flex items-center gap-2">
            <div className="w-6 h-1 rounded bg-amber-500"></div>
            <span className="text-xs text-slate-400">Balanced Alternative</span>
          </div>
          <div className="flex items-center gap-2">
            <div className="w-6 h-1 rounded bg-red-500"></div>
            <span className="text-xs text-slate-400">Congested (Avoid)</span>
          </div>
        </div>
      </div>
    </div>
  );
}
