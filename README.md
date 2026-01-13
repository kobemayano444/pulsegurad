# PulseGuard — API Rate Limiter + Live Dashboard

PulseGuard is a production-style rate limiting service built with **FastAPI** and **Redis**. It blocks abusive traffic using real rate limiting algorithms and exposes a clean, human-friendly dashboard.

## What you get
- **Two algorithms**: Fixed Window and Token Bucket (switchable via an environment variable)
- **Per-client identification**: API key header (`x-api-key`) or fallback to client IP
- **Live metrics**: allowed vs blocked requests + top blocked clients
- **Admin reset** endpoint for demos
- **Pretty UI**: Tailwind CDN + Chart.js, no frontend build step

---

## Quick start (Docker Compose)
```bash
cd PulseGuard
docker compose up --build
```
Then open:
- Home: `http://127.0.0.1:8000`
- Dashboard: `http://127.0.0.1:8000/dashboard`
- Swagger: `http://127.0.0.1:8000/docs`

---

## Quick start (Local)
1) Install dependencies
```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

2) Start Redis (Docker recommended)
```bash
docker run -p 6379:6379 redis:7
```

3) Run the API
```bash
uvicorn app.main:app --reload
```

---

## How rate limiting works
### Fixed Window (baseline)
Counts requests in a time window (e.g., 60 seconds). Fast and simple.

### Token Bucket (smoother)
Allows bursts up to capacity, then refills tokens over time. Implemented atomically via a Redis Lua script.

Switch algorithms:
```bash
export RATE_LIMIT_ALGO=token_bucket
# or
export RATE_LIMIT_ALGO=fixed_window
```

---

## Try it
### 1) Ping the API
```bash
curl -i http://127.0.0.1:8000/api/ping
```

### 2) Simulate a client via API key
```bash
curl -i -H "x-api-key: DEMO123" http://127.0.0.1:8000/api/ping
```

### 3) Load test (generates some 429s)
```bash
python scripts/load_test.py --url http://127.0.0.1:8000/api/ping --clients 5 --requests 250
```

---

## Environment variables
See `.env.example`.

Common ones:
- `RATE_LIMIT_ALGO`: `fixed_window` or `token_bucket`
- `DEFAULT_LIMIT`: requests per window (fixed window)
- `WINDOW_SECONDS`: window size in seconds
- `TB_CAPACITY`: max burst size (token bucket)
- `TB_REFILL_PER_SEC`: refill speed (token bucket)
- `TIERS`: optional per-api-key limits like `DEMO123=120,DEMO456=300`

---

---

## Notes
This repo is intentionally "portfolio-ready": clean structure, real infra concept, live dashboard, and a load generator.
