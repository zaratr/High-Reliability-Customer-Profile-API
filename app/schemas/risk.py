from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field


class RiskSignalCreate(BaseModel):
    signal_type: str
    payload: dict[str, Any]
    source_system: str
    request_id: Optional[str] = Field(None, description="Idempotency key")


class RiskSignalRead(BaseModel):
    id: int
    customer_id: int
    signal_type: str
    payload: dict[str, Any]
    source_system: str
    request_id: str
    received_at: datetime

    class Config:
        from_attributes = True
