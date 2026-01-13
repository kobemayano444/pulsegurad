from __future__ import annotations

import os

APP_NAME = os.getenv("APP_NAME", "PulseGuard")

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

# Algorithm switch
RATE_LIMIT_ALGO = os.getenv("RATE_LIMIT_ALGO", "fixed_window").strip().lower()  # fixed_window | token_bucket

# Fixed window defaults
DEFAULT_LIMIT = int(os.getenv("DEFAULT_LIMIT", "60"))
WINDOW_SECONDS = int(os.getenv("WINDOW_SECONDS", "60"))

# Token bucket defaults
TB_CAPACITY = int(os.getenv("TB_CAPACITY", "30"))
TB_REFILL_PER_SEC = float(os.getenv("TB_REFILL_PER_SEC", "1.0"))

# Optional per-key tiers (simple demo)
# Format: KEY1=120,KEY2=300 (requests per window for fixed-window)
TIERS_RAW = os.getenv("TIERS", "").strip()


def parse_tiers(raw: str) -> dict[str, int]:
    """Parse TIERS env var: KEY1=120,KEY2=300 -> {"KEY1":120, "KEY2":300}."""
    tiers: dict[str, int] = {}
    if not raw:
        return tiers
    for item in raw.split(","):
        item = item.strip()
        if not item or "=" not in item:
            continue
        k, v = item.split("=", 1)
        k = k.strip()
        v = v.strip()
        if not k or not v:
            continue
        try:
            tiers[k] = int(v)
        except ValueError:
            continue
    return tiers


TIERS = parse_tiers(TIERS_RAW)
