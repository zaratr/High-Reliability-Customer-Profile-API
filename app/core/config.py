from functools import lru_cache
from typing import List

from pydantic import AnyHttpUrl, BaseSettings, Field


class Settings(BaseSettings):
    app_name: str = "High-Reliability Customer Profile API"
    environment: str = "dev"
    debug: bool = False

    database_url: str = Field(..., description="PostgreSQL connection string")
    redis_url: str = Field(..., description="Redis connection string")

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
