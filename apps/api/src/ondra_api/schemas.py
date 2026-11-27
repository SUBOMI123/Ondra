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
    mfa_required: bool = False  # Clerk sign-in: their role needs two-step sign-in and they haven't used it


class IdentityOut(_Out):
    kind: str
    value: str


class ContactOut(_Out):
    id: uuid.UUID
    display_name: str
    is_vip: bool
    vip_owner_user_id: uuid.UUID | None = None  # who looks after this VIP (null: the owner)
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
    phone: str | None = None  # where Ondra puts calls through to them
    # Routing: their own hours and time zone (null: the dealership's) and a limit on open tasks (null: none).
    work_hours: dict | None = None
    timezone: str | None = None
    max_open_tasks: int | None = None


class Page[T](BaseModel):
    items: list[T]
    total: int


class TeamPage(Page[UserOut]):
    counts: dict[str, dict[str, int]]  # {"role": {...}, "status": {"active", "invited", "deactivated"}} for the whole team
