from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from redis import Redis


@dataclass
class ClientStats:
    allowed: int
    blocked: int


class MetricsStore:
    """Stores lightweight metrics in Redis.

    - Global: metrics:global (hash)
    - Per client: metrics:client:{client_id} (hash)
    - Top blocked clients: metrics:top_blocked (sorted set)

    This is intentionally simple and cheap.
    """

    GLOBAL_KEY = "metrics:global"
    TOP_BLOCKED_ZSET = "metrics:top_blocked"

    def __init__(self, r: Redis):
        self.r = r

    def _client_key(self, client_id: str) -> str:
        return f"metrics:client:{client_id}"

    def record_allowed(self, client_id: str) -> None:
        pipe = self.r.pipeline()
        pipe.hincrby(self.GLOBAL_KEY, "allowed", 1)
        pipe.hincrby(self._client_key(client_id), "allowed", 1)
        pipe.execute()

    def record_blocked(self, client_id: str) -> None:
        pipe = self.r.pipeline()
        pipe.hincrby(self.GLOBAL_KEY, "blocked", 1)
        pipe.hincrby(self._client_key(client_id), "blocked", 1)
        pipe.zincrby(self.TOP_BLOCKED_ZSET, 1, client_id)
        pipe.execute()

    def global_stats(self) -> dict[str, int]:
        data: dict[str, Any] = self.r.hgetall(self.GLOBAL_KEY) or {}
        return {
            "allowed": int(data.get("allowed", 0)),
            "blocked": int(data.get("blocked", 0)),
        }

    def top_blocked(self, n: int = 10) -> list[dict[str, Any]]:
        # Returns list of {client_id, blocked}
        raw = self.r.zrevrange(self.TOP_BLOCKED_ZSET, 0, max(0, n - 1), withscores=True)
        return [{"client_id": cid, "blocked": int(score)} for cid, score in raw]

    def client_stats(self, client_id: str) -> ClientStats:
        data = self.r.hgetall(self._client_key(client_id)) or {}
        return ClientStats(
            allowed=int(data.get("allowed", 0)),
            blocked=int(data.get("blocked", 0)),
        )
