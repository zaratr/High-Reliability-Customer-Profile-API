import time
from typing import Optional

import redis
from fastapi import HTTPException, status


class RateLimiter:
    def __init__(self, redis_client: redis.Redis, default_limit: int = 100):
        self.redis = redis_client
        self.default_limit = default_limit

    def check(self, key: str, limit: Optional[int] = None) -> None:
        limit = limit or self.default_limit
        bucket = f"rate:{key}:{int(time.time() // 60)}"
        current = self.redis.incr(bucket)
        if current == 1:
            self.redis.expire(bucket, 60)
        if current > limit:
            ttl = self.redis.ttl(bucket)
            retry_after = ttl if ttl > 0 else 60
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="rate limit exceeded",
                headers={"Retry-After": str(retry_after)},
            )
