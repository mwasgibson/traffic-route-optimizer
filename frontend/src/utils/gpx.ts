import type { Coordinates } from "@/types";

export function buildGpx(
  name: string,
  route: Coordinates[],
  waypoints: Coordinates[] = [],
): string {
  const esc = (s: string) =>
    s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
  const wpts = waypoints
    .map(
      (c, i) =>
        `    <wpt lat="${c.lat}" lon="${c.lon}"><name>Stop ${i + 1}</name></wpt>`,
    )
    .join("\n");
  const trkpts = route
    .map((c) => `        <trkpt lat="${c.lat}" lon="${c.lon}"></trkpt>`)
    .join("\n");
  return `<?xml version="1.0" encoding="UTF-8"?>
<gpx version="1.1" creator="TrafficRouteOptimizer" xmlns="http://www.topografix.com/GPX/1/1">
  <metadata><name>${esc(name)}</name></metadata>
${wpts}
  <trk><name>${esc(name)}</name>
    <trkseg>
${trkpts}
    </trkseg>
  </trk>
</gpx>`;
}

export function downloadGpx(filename: string, gpx: string): void {
  const blob = new Blob([gpx], { type: "application/gpx+xml" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}
