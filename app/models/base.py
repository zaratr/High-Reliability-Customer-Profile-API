from datetime import datetime

from sqlalchemy.orm import DeclarativeBase, declared_attr


class Base(DeclarativeBase):
    @declared_attr.directive
    def __tablename__(cls) -> str:  # type: ignore[misc]
        return cls.__name__.lower()

    created_at = None
    updated_at = None


class TimestampMixin:
    created_at = None
    updated_at = None

    @declared_attr
    def created_at(cls):  # type: ignore[misc]
        from sqlalchemy import Column, DateTime, func

        return Column(DateTime(timezone=True), nullable=False, server_default=func.now())

    @declared_attr
    def updated_at(cls):  # type: ignore[misc]
        from sqlalchemy import Column, DateTime, func

        return Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())
