from __future__ import annotations

import time
from dataclasses import dataclass

from redis import Redis

from .config import WINDOW_SECONDS, TB_CAPACITY, TB_REFILL_PER_SEC


@dataclass
class Decision:
    allowed: bool
    remaining: int
    reset_in_sec: int
    limit: int
    algo: str


class FixedWindowLimiter:
    """Fixed Window rate limiter.

    Counts requests in fixed-length windows aligned to UNIX time.
    This is a great baseline; token bucket is smoother for bursts.
    """

    def __init__(self, r: Redis):
        self.r = r

    def decide(self, client_id: str, limit: int, now_ts: int | None = None) -> Decision:
        now_ts = int(time.time()) if now_ts is None else int(now_ts)
        window_start = now_ts - (now_ts % WINDOW_SECONDS)
        key = f"rl:fw:{client_id}:{window_start}"

        # Atomic increment
        count = self.r.incr(key)
        if count == 1:
            # First hit in this window: set expiration so Redis cleans up.
            self.r.expire(key, WINDOW_SECONDS)

        remaining = max(0, limit - int(count))
        reset_in = max(0, WINDOW_SECONDS - (now_ts - window_start))
        allowed = int(count) <= limit
        return Decision(
            allowed=allowed,
            remaining=remaining,
            reset_in_sec=reset_in,
            limit=limit,
            algo="fixed_window",
        )


_TOKEN_BUCKET_LUA = r"""
-- Token bucket in Redis (atomic).
-- KEYS[1] = bucket key
-- ARGV[1] = capacity (int)
-- ARGV[2] = refill_per_sec (float)
-- ARGV[3] = now_ts (int, seconds)

local key = KEYS[1]
local capacity = tonumber(ARGV[1])
local refill_per_sec = tonumber(ARGV[2])
local now = tonumber(ARGV[3])

local data = redis.call('HMGET', key, 'tokens', 'last')
local tokens = tonumber(data[1])
local last = tonumber(data[2])

if tokens == nil then
  tokens = capacity
end
if last == nil then
  last = now
end

-- Refill tokens based on time passed
local elapsed = now - last
if elapsed < 0 then
  elapsed = 0
end
local refill = elapsed * refill_per_sec
local new_tokens = tokens + refill
if new_tokens > capacity then
  new_tokens = capacity
end

local allowed = 0
if new_tokens >= 1 then
  allowed = 1
  new_tokens = new_tokens - 1
end

-- Update bucket state
redis.call('HMSET', key, 'tokens', tostring(new_tokens), 'last', tostring(now))
redis.call('EXPIRE', key, 3600)

return {allowed, new_tokens, capacity}
"""


class TokenBucketLimiter:
    """Token bucket limiter.

    Smoother than fixed window: supports bursts up to capacity, then refills.
    """

    def __init__(self, r: Redis, capacity: int = TB_CAPACITY, refill_per_sec: float = TB_REFILL_PER_SEC):
        self.r = r
        self.capacity = int(capacity)
        self.refill_per_sec = float(refill_per_sec)
        self._lua = self.r.register_script(_TOKEN_BUCKET_LUA)

    def decide(self, client_id: str, now_ts: int | None = None) -> Decision:
        now_ts = int(time.time()) if now_ts is None else int(now_ts)
        key = f"rl:tb:{client_id}"

        allowed, tokens_left, capacity = self._lua(
            keys=[key],
            args=[self.capacity, self.refill_per_sec, now_ts],
        )

        tokens_left = float(tokens_left)
        # Next reset is approximate: how long to get 1 token if empty
        reset_in = 0 if tokens_left >= 1 else int(1 / max(self.refill_per_sec, 1e-6))

        return Decision(
            allowed=int(allowed) == 1,
            remaining=int(tokens_left),
            reset_in_sec=reset_in,
            limit=self.capacity,
            algo="token_bucket",
        )


def build_limiter(r: Redis, algo: str):
    algo = (algo or "fixed_window").strip().lower()
    if algo == "token_bucket":
        return TokenBucketLimiter(r)
    return FixedWindowLimiter(r)
