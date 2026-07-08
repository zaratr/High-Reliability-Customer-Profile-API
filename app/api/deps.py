import logging
from typing import Optional

import redis
from fastapi import Depends
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.edge_client import EdgeDbClient
from app.db.session import get_db

logger = logging.getLogger(__name__)

settings = get_settings()
redis_client = redis.Redis.from_url(settings.redis_url, decode_responses=False)

# Lazily-created edge read-replica client (None when EDGE_DB_URL is unset).
_edge_db: Optional[EdgeDbClient] = None


def get_redis() -> redis.Redis:
    return redis_client


def get_db_session() -> Session:
    yield from get_db()


def get_edge_db() -> Optional[EdgeDbClient]:
    """Return the shared edge read-replica client, or None if not configured.

    Construction is lazy so the app boots without a Turso instance — the client
    only connects on first query.
    """
    global _edge_db
    if settings.edge_db_url is None:
        return None
    if _edge_db is None:
        _edge_db = EdgeDbClient(settings.edge_db_url, settings.edge_db_token)
    return _edge_db
