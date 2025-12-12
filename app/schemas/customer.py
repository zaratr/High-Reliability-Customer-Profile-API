from datetime import datetime
from typing import Optional

from pydantic import BaseModel, EmailStr, Field


class AddressCreate(BaseModel):
    line1: str
    line2: Optional[str] = None
    city: str
    state: str
    postal_code: str
    country: str


class AddressRead(AddressCreate):
    id: int
    created_at: datetime
    updated_at: datetime


class CustomerCreate(BaseModel):
    name: str
    email: EmailStr
    phone: str
    addresses: list[AddressCreate] = []


class CustomerUpdate(BaseModel):
    name: Optional[str] = None
    phone: Optional[str] = None
    status: Optional[str] = Field(None, pattern="^(active|inactive)$")


class CustomerRead(BaseModel):
    id: int
    name: str
    email: EmailStr
    phone: str
    status: str
    addresses: list[AddressRead] = []
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
