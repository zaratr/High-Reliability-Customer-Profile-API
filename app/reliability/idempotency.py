import redis
from fastapi import HTTPException, status


class IdempotencyService:
    def __init__(self, redis_client: redis.Redis, ttl_seconds: int = 600):
        self.redis = redis_client
        self.ttl_seconds = ttl_seconds

    def check_and_set(self, key: str, response_payload: str | None = None) -> str | None:
        existing = self.redis.get(key)
        if existing:
            return existing.decode()
        pipe = self.redis.pipeline()
        pipe.setnx(key, response_payload or "processing")
        pipe.expire(key, self.ttl_seconds)
        success, _ = pipe.execute()
        if not success:
            existing = self.redis.get(key)
            if existing:
                return existing.decode()
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="conflict")
        return None

    def store_response(self, key: str, response_payload: str) -> None:
        self.redis.setex(key, self.ttl_seconds, response_payload)
