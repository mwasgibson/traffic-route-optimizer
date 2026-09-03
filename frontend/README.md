# Traffic Route Optimizer — Frontend

React + TypeScript + Tailwind CSS + Leaflet dashboard for route optimization visualization.

## Setup

```bash
cd frontend
npm install
```

## Development

```bash
npm run dev
```

The dev server runs on `http://localhost:5173` and proxies API calls to `http://localhost:8000`.

## Build

```bash
npm run build
```

Output goes to `dist/` for deployment.

## Tech Stack

- **React 18** — UI framework
- **TypeScript** — Type safety
- **Tailwind CSS** — Styling
- **Leaflet + React-Leaflet** — Interactive maps
- **Recharts** — Data visualization
- **Axios** — HTTP client
- **Vite** — Build tool

## Project Structure

```text
src/
├── components/
│   ├── RouteMap.tsx           # Leaflet map with route visualization
│   ├── RoutePanel.tsx          # Left sidebar with controls & route cards
│   ├── RouteComparison.tsx     # Table/chart/radar comparison views
│   ├── TrafficDensityChart.tsx # Hourly congestion forecast
│   ├── AIInsights.tsx          # AI-generated recommendations
│   └── CostAnalysis.tsx        # Fuel & environmental cost breakdown
├── pages/
│   └── Dashboard.tsx           # Main layout composition
├── hooks/
│   └── useRouteOptimization.ts # Data fetching hook
├── services/
│   └── api.ts                  # Axios API client
├── types/
│   └── index.ts                # TypeScript interfaces
├── App.tsx                     # Router setup
└── main.tsx                    # Entry point
```
