import redis
from fastapi import Depends
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.session import get_db


settings = get_settings()
redis_client = redis.Redis.from_url(settings.redis_url, decode_responses=False)


def get_redis() -> redis.Redis:
    return redis_client


def get_db_session() -> Session:
    yield from get_db()
