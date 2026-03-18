import asyncio
import time
from config import MAX_REQUESTS_PER_MINUTE


class RateLimiter:
    def __init__(self, max_per_minute: int = MAX_REQUESTS_PER_MINUTE):
        self.max_per_minute = max_per_minute
        self.requests: list[float] = []

    async def acquire(self):
        now = time.time()
        self.requests = [t for t in self.requests if now - t < 60]
        if len(self.requests) >= self.max_per_minute:
            oldest = self.requests[0]
            wait_time = 60 - (now - oldest)
            if wait_time > 0:
                await asyncio.sleep(wait_time)
            self.requests = [t for t in self.requests if time.time() - t < 60]
        self.requests.append(time.time())

    def get_stats(self) -> dict:
        now = time.time()
        recent = [t for t in self.requests if now - t < 60]
        return {
            "requests_last_minute": len(recent),
            "available": self.max_per_minute - len(recent),
            "max_per_minute": self.max_per_minute,
        }


rate_limiter = RateLimiter()
