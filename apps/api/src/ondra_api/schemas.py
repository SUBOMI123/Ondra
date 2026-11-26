import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict


class _Out(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class MeOut(_Out):
    id: uuid.UUID
    email: str
    name: str
    role: str
    tenant_id: uuid.UUID
    tenant_name: str
    phone: str | None = None


class IdentityOut(_Out):
    kind: str
    value: str


class ContactOut(_Out):
    id: uuid.UUID
    display_name: str
    is_vip: bool
    preferred_channel: str | None
    language: str | None
    tags: list[str]
    identities: list[IdentityOut] = []
    created_at: datetime


class VehicleOut(_Out):
    id: uuid.UUID
    stock_number: str
    vin: str | None
    year: int
    make: str
    model: str
    trim: str | None
    price: Decimal | None
    mileage: int | None
    status: str


class UserOut(_Out):
    id: uuid.UUID
    email: str
    name: str
    role: str
    active: bool
    invited: bool = False  # hasn't set a password yet


class Page[T](BaseModel):
    items: list[T]
    total: int
