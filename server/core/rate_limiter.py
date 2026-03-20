import time
from config import MAX_REQUESTS_PER_MINUTE


class RateLimiter:
    """
    Lightweight request counter.
    Set MAX_REQUESTS_PER_MINUTE=0 (default) to disable throttling entirely.
    A non-zero value re-enables the limit (useful for cost control).
    """

    def __init__(self, max_per_minute: int = MAX_REQUESTS_PER_MINUTE):
        self.max_per_minute = max_per_minute
        self.requests: list[float] = []

    async def acquire(self):
        # Track for stats even when unlimited
        self.requests.append(time.time())
        now = time.time()
        self.requests = [t for t in self.requests if now - t < 60]

    def get_stats(self) -> dict:
        now = time.time()
        recent = [t for t in self.requests if now - t < 60]
        unlimited = self.max_per_minute == 0
        return {
            "requests_last_minute": len(recent),
            "available": None if unlimited else self.max_per_minute - len(recent),
            "max_per_minute": "unlimited" if unlimited else self.max_per_minute,
            "throttling": not unlimited,
        }


rate_limiter = RateLimiter()
