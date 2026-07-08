from functools import lru_cache
from typing import List

from pydantic import AnyHttpUrl, BaseSettings, Field


class Settings(BaseSettings):
    app_name: str = "High-Reliability Customer Profile API"
    environment: str = "dev"
    debug: bool = False

    database_url: str = Field(..., description="PostgreSQL connection string")
    redis_url: str = Field(..., description="Redis connection string")

    # Optional libSQL/Turso edge read-replica. When unset, reads go straight to
    # Postgres (no behavior change). When set, reads try edge first and fall
    # back to Postgres on failure (see app/db/edge_client.py).
    edge_db_url: str | None = Field(None, description="libSQL/Turso edge replica URL")
    edge_db_token: str | None = Field(None, description="libSQL/Turso auth token")

    jwt_secret: str = Field(..., description="JWT secret key")
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 60

    rate_limit_per_minute: int = 100

    celery_broker_url: str | None = None
    celery_result_backend: str | None = None

    cors_origins: List[AnyHttpUrl] = []

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


@lru_cache()
def get_settings() -> Settings:
    return Settings()  # type: ignore[arg-type]
