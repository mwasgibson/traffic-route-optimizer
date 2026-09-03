# Traffic Route Optimizer (Production Ready)

An intelligent route optimization system using **real-world APIs** for traffic, weather, and routing data.

## Real Data Sources

| Service | Data | Free Tier |
| --------- | ------ | ----------- |
| **OpenWeatherMap** | Current weather, temperature, visibility, wind | 1,000 calls/day |
| **TomTom Traffic** | Real-time traffic flow, congestion, incidents | 2,500 transactions/day |
| **OpenRouteService** | Real route geometry, distances, durations | 2,000 directions/day |
| **OpenStreetMap/Nominatim** | Worldwide geocoding & reverse geocoding | 1 req/sec |

## Quick Start

### 1. Get API Keys (All Free)

1. **OpenWeatherMap**: [openweathermap.org/api](https://openweathermap.org/api) → Sign up → My API Keys
2. **TomTom**: [developer.tomtom.com](https://developer.tomtom.com) → Register → Create App
3. **OpenRouteService**: [openrouteservice.org/dev](https://openrouteservice.org/dev/#/login) → Sign up → API Keys

### 2. Backend

```bash
cd backend
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# Add your real API keys to .env
uvicorn app.main:app --reload
```

### 3. Frontend

```bash
cd frontend
npm install
npm run dev
```

## Features

- **Real Weather Data** — Live temperature, rainfall, visibility, wind from OpenWeatherMap
- **Real Traffic Data** — Live congestion levels from TomTom Traffic API
- **Real Route Geometry** — Actual road paths from OpenRouteService (not straight lines)
- **Real Geocoding** — Worldwide location search via Nominatim (OpenStreetMap)
- **Multi-factor Scoring** — Time, distance, safety, fuel, weather weighted optimization
- **AI Insights** — Auto-generated savings analysis and warnings

## API Endpoints

| Endpoint | Description |
| ---------- | ------------- |
| `POST /api/v1/routes/optimize` | Optimize with real traffic & weather |
| `GET /api/v1/routes/search?q=...` | Search real locations worldwide |
| `GET /api/v1/routes/reverse-geocode?lat=...&lon=...` | GPS to real address |
| `GET /api/v1/routes/heatmap` | Traffic congestion heatmap |

## Environment Variables

```env
OPENWEATHER_API_KEY=your_key      # Required
TOMTOM_API_KEY=your_key           # Required
OPENROUTE_API_KEY=your_key        # Required for real route geometry
REDIS_URL=redis://localhost:6379/0 # Optional caching
```

## License

MIT
