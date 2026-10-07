# Traffic Route Optimizer — Backend (Production)

FastAPI-based backend with **real API integrations** for production use.

## Data Sources

| Service | Purpose | Free Tier | Sign Up |
| --------- | --------- | ----------- | --------- |
| **OpenWeatherMap** | Current weather conditions | 1,000 calls/day | [openweathermap.org/api](https://openweathermap.org/api) |
| **TomTom** | Real-time traffic flow data | 2,500 transactions/day | [developer.tomtom.com](https://developer.tomtom.com) |
| **OSRM** | Route directions & geometry | Public demo | [project-osrm.org](http://project-osrm.org/) |
| **OpenRouteService** | Optional future routing | 2,000 directions/day | [openrouteservice.org](https://openrouteservice.org/dev/#/login) |
| **OpenStreetMap/Nominatim** | Geocoding & reverse geocoding | 1 request/second | Built-in (no key needed) |

## Quick Start

```bash
cd backend
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Copy and fill in your API keys
cp .env.example .env
# Edit .env with real API keys

# Run
uvicorn app.main:app --reload --port 8000
```

## API Endpoints

| Method | Endpoint | Description |
| -------- | ---------- | ------------- |
| POST | `/api/v1/routes/optimize` | Optimize routes with real traffic & weather |
| GET | `/api/v1/routes/heatmap` | Traffic heatmap for region |
| GET | `/api/v1/routes/search` | Search locations (Nominatim) |
| GET | `/api/v1/routes/reverse-geocode` | Coordinates to address (Nominatim) |

## Testing

```bash
pytest tests/ -v
```

## Architecture

```text
app/
├── main.py              # FastAPI entry point
├── core/
│   └── config.py        # Settings & environment
├── models/
│   └── schemas.py       # Pydantic models
├── routers/
│   └── routes.py        # API endpoints (Nominatim geocoding)
└── services/
    ├── weather_service.py    # OpenWeatherMap (REAL)
    ├── traffic_service.py    # TomTom Traffic (REAL)
    └── route_optimizer.py    # OSRM geometry + multi-factor scoring
```

## Production Deployment

```bash
# With Docker
docker build -t traffic-backend .
docker run -p 8000:8000 --env-file .env traffic-backend

# With Gunicorn + Uvicorn workers
uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4
```
