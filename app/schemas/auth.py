from datetime import datetime
from typing import List

from pydantic import BaseModel


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class TokenData(BaseModel):
    username: str
    scopes: List[str]


class APIKeyCreate(BaseModel):
    client_id: str
    name: str
    scopes: List[str]
    enabled: bool = True


class APIKeyRead(APIKeyCreate):
    hashed_key: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
