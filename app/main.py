from __future__ import annotations

import time
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from redis import Redis

from .config import APP_NAME, DEFAULT_LIMIT, RATE_LIMIT_ALGO, TIERS, REDIS_URL
from .limiter import build_limiter
from .metrics import MetricsStore

BASE_DIR = Path(__file__).resolve().parent.parent

app = FastAPI(title=APP_NAME)

# Templates + static
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")

# Runtime singletons
redis_client = Redis.from_url(REDIS_URL, decode_responses=True)
limiter = build_limiter(redis_client, RATE_LIMIT_ALGO)
metrics = MetricsStore(redis_client)


def get_client_id(req: Request) -> str:
    """Identify a client. Prefer x-api-key; fallback to IP."""
    api_key = req.headers.get("x-api-key")
    if api_key:
        return f"key:{api_key.strip()}"
    # NOTE: in real systems, use X-Forwarded-For when behind a proxy.
    return f"ip:{req.client.host}"


def get_limit_for_client(req: Request) -> int:
    """Return request limit for a client (fixed-window algo)."""
    api_key = req.headers.get("x-api-key")
    if api_key and api_key.strip() in TIERS:
        return int(TIERS[api_key.strip()])
    return DEFAULT_LIMIT


@app.middleware("http")
async def rate_limit_middleware(request: Request, call_next):
    # Let the landing page and static assets stay unthrottled (nice UX).
    # In real production, you'd likely limit everything except health checks.
    if request.url.path in {"/", "/dashboard"} or request.url.path.startswith("/static"):
        return await call_next(request)

    client_id = get_client_id(request)

    now_ts = int(time.time())
    if limiter.__class__.__name__ == "FixedWindowLimiter":
        limit = get_limit_for_client(request)
        decision = limiter.decide(client_id, limit=limit, now_ts=now_ts)
    else:
        decision = limiter.decide(client_id, now_ts=now_ts)

    if not decision.allowed:
        metrics.record_blocked(client_id)
        headers = {
            "Retry-After": str(decision.reset_in_sec),
            "X-RateLimit-Limit": str(decision.limit),
            "X-RateLimit-Remaining": "0",
            "X-RateLimit-Reset": str(decision.reset_in_sec),
            "X-RateLimit-Algorithm": decision.algo,
        }
        return JSONResponse(status_code=429, content={"detail": "Rate limit exceeded"}, headers=headers)

    metrics.record_allowed(client_id)
    response = await call_next(request)
    response.headers["X-RateLimit-Limit"] = str(decision.limit)
    response.headers["X-RateLimit-Remaining"] = str(decision.remaining)
    response.headers["X-RateLimit-Reset"] = str(decision.reset_in_sec)
    response.headers["X-RateLimit-Algorithm"] = decision.algo
    return response


# --- UI routes ---
@app.get("/", response_class=HTMLResponse)
def index(request: Request):
    return templates.TemplateResponse(
        "index.html",
        {
            "request": request,
            "app_name": APP_NAME,
            "algo": RATE_LIMIT_ALGO,
            "default_limit": DEFAULT_LIMIT,
        },
    )


@app.get("/dashboard", response_class=HTMLResponse)
def dashboard(request: Request):
    return templates.TemplateResponse(
        "dashboard.html",
        {
            "request": request,
            "app_name": APP_NAME,
            "algo": RATE_LIMIT_ALGO,
        },
    )


# --- API routes ---
@app.get("/api/ping")
def ping():
    return {"ok": True, "message": "pong"}


@app.get("/api/metrics")
def api_metrics():
    data = metrics.global_stats()
    data["algo"] = RATE_LIMIT_ALGO
    data["default_limit"] = DEFAULT_LIMIT
    data["tiers"] = TIERS
    data["top_blocked"] = metrics.top_blocked(8)
    return data


@app.get("/api/admin/clients/{client_id}")
def client_stats(client_id: str):
    # Simple admin endpoint (in real life, protect this!)
    stats = metrics.client_stats(client_id)
    return {"client_id": client_id, "allowed": stats.allowed, "blocked": stats.blocked}


@app.post("/api/admin/reset")
def reset_metrics():
    # Simple reset for demos
    redis_client.delete(metrics.GLOBAL_KEY)
    redis_client.delete(metrics.TOP_BLOCKED_ZSET)
    # Delete per-client keys can be heavy; for the demo we leave them.
    return {"ok": True, "message": "metrics reset"}


@app.get("/api/health")
def health():
    try:
        redis_client.ping()
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"redis unreachable: {e}")
    return {"ok": True}
