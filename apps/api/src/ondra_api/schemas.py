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
    timezone: str = "America/Chicago"  # the dealership's: every time in the dashboard is shown in it
    phone: str | None = None
    mfa_required: bool = False  # Clerk sign-in: their role needs two-step sign-in and they haven't used it


class IdentityOut(_Out):
    kind: str
    value: str


class ContactOut(_Out):
    id: uuid.UUID
    display_name: str
    is_vip: bool
    vip_owner_user_id: uuid.UUID | None = None  # who looks after this VIP
    name_source: str | None = None  # 'call': as Ondra heard it on a call (check the spelling), 'typed', 'staff
    preferred_channel: str | None
    language: str | None
    tags: list[str]
    identities: list[IdentityOut] = []
    created_at: datetime


class ClientDealOut(BaseModel):
    type: str
    stage: str
    vehicle: str | None
    budget_max: float | None


class ClientRowOut(ContactOut):
    """A row of the Clients list: who they are, plus where they stand with the dealership."""
    last_contact_at: datetime | None = None
    deal: ClientDealOut | None = None
    looks_after: str | None = None  # the deal's salesperson, else the VIP's handler, else whoever has the conversation or an open task


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
    photos: list[str] = []
    created_at: datetime | None = None  # first seen: when it came onto the lot (or into Ondra)


class VehicleRowOut(VehicleOut):
    """A row of the Inventory list: the car, plus how long it's sat and how many buyers are asking about it."""
    days_on_lot: int = 0
    asked_about: int = 0  # open deals that name this car (by stock number, or year, make and model)
    hold: dict | None = None  # {by, at, for}: who put it on hold, when, and for which client


class VehiclePage(BaseModel):
    items: list[VehicleRowOut]
    total: int
    makes: list[str]  # for the make filter: every make on the lot, not just this page
    can_hold: bool = False  # put on hold and release: anyone who sells
    can_sell: bool = False  # mark sold: managers and the owner


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
