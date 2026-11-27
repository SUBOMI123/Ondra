"""Ondra's data model (BUILD_PLAN.md §5).

Every table except `tenants` carries `tenant_id`, and Postgres row-level security restricts every row to the
tenant set for the current transaction (see `TENANT_TABLES` and the migration). Status-like fields are text with
CHECK constraints rather than Postgres enums, so adding a value is a one-line migration.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import ARRAY, CITEXT, JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def _in(col: str, values: tuple[str, ...]) -> str:
    return f"{col} IN ({', '.join(repr(v) for v in values)})"


ROLES = ("owner", "admin", "manager", "sales", "service", "ops", "viewer")
CHANNELS = ("phone", "whatsapp", "sms", "email", "instagram")


class Base(DeclarativeBase):
    pass


class Timestamped:
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class TenantScoped(Timestamped):
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), index=True,
        # Filled from the transaction's tenant setting when the API doesn't pass it explicitly.
        server_default=text("NULLIF(current_setting('app.tenant_id', true), '')::uuid"),
    )


class Tenant(Base, Timestamped):
    __tablename__ = "tenants"
    name: Mapped[str] = mapped_column(String(200))
    timezones: Mapped[list[str]] = mapped_column(ARRAY(Text), server_default=text("ARRAY['America/Chicago']"))
    locale: Mapped[str] = mapped_column(String(20), server_default="en-US")
    business_hours: Mapped[dict] = mapped_column(JSONB, server_default=text("'{}'::jsonb"))
    plan: Mapped[str] = mapped_column(String(40), server_default="pilot")
    settings: Mapped[dict] = mapped_column(JSONB, server_default=text("'{}'::jsonb"))
    clerk_org_id: Mapped[str | None] = mapped_column(String(64), unique=True)  # the dealership's Clerk Organization


class User(Base, TenantScoped):
    __tablename__ = "users"
    __table_args__ = (
        CheckConstraint(_in("role", ROLES), name="users_role"),
        # Emails are unique across tenants so sign-in can find the account before the tenant is known.
        UniqueConstraint("email", name="users_email_key"),
    )
    email: Mapped[str] = mapped_column(CITEXT)
    name: Mapped[str] = mapped_column(String(200))
    role: Mapped[str] = mapped_column(String(20))
    phone: Mapped[str | None] = mapped_column(String(32))
    clerk_user_id: Mapped[str | None] = mapped_column(String(64), unique=True)  # linked on their first Clerk sign-in
    password_hash: Mapped[str | None] = mapped_column(Text)
    notification_prefs: Mapped[dict] = mapped_column(JSONB, server_default=text("'{}'::jsonb"))
    active: Mapped[bool] = mapped_column(Boolean, server_default=text("true"))
    invite_token_hash: Mapped[str | None] = mapped_column(String(64), unique=True)
    invite_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # Routing (ondra_core.routing): their own hours and timezone (null: the dealership's), a limit on open tasks
    # (null: none), and when they were last given work, for round-robin.
    timezone: Mapped[str | None] = mapped_column(String(64))
    work_hours: Mapped[dict | None] = mapped_column(JSONB)
    max_open_tasks: Mapped[int | None] = mapped_column(Integer)
    last_assigned_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Session(Base, TenantScoped):
    """Refresh sessions. Only a hash of the refresh token is stored."""

    __tablename__ = "sessions"
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"))
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    user_agent: Mapped[str | None] = mapped_column(Text)
    ip: Mapped[str | None] = mapped_column(String(64))


class Contact(Base, TenantScoped):
    __tablename__ = "contacts"
    display_name: Mapped[str] = mapped_column(String(200))
    is_vip: Mapped[bool] = mapped_column(Boolean, server_default=text("false"))
    vip_owner_user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))
    preferred_channel: Mapped[str | None] = mapped_column(String(20))
    language: Mapped[str | None] = mapped_column(String(20))
    tags: Mapped[list[str]] = mapped_column(ARRAY(Text), server_default=text("'{}'"))
    notes: Mapped[str | None] = mapped_column(Text)
    merged_into_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("contacts.id"))


class ContactIdentity(Base, TenantScoped):
    __tablename__ = "contact_identities"
    __table_args__ = (
        CheckConstraint(_in("kind", ("phone", "whatsapp", "email", "instagram")), name="contact_identities_kind"),
        UniqueConstraint("tenant_id", "kind", "value", name="contact_identities_unique"),
    )
    contact_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("contacts.id", ondelete="CASCADE"), index=True)
    kind: Mapped[str] = mapped_column(String(20))
    value: Mapped[str] = mapped_column(String(320))  # E.164 for phones, lowercased for email
    verified: Mapped[bool] = mapped_column(Boolean, server_default=text("false"))


class ContactRelation(Base, TenantScoped):
    __tablename__ = "contact_relations"
    contact_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("contacts.id", ondelete="CASCADE"))
    related_contact_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("contacts.id", ondelete="CASCADE"))
    relation: Mapped[str] = mapped_column(String(40))  # assistant, manager, spouse


class Consent(Base, TenantScoped):
    __tablename__ = "consents"
    __table_args__ = (
        CheckConstraint(_in("purpose", ("transactional", "marketing")), name="consents_purpose"),
        CheckConstraint(_in("status", ("opted_in", "opted_out")), name="consents_status"),
    )
    contact_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("contacts.id", ondelete="CASCADE"), index=True)
    channel: Mapped[str] = mapped_column(String(20))
    purpose: Mapped[str] = mapped_column(String(20))
    status: Mapped[str] = mapped_column(String(20))
    source: Mapped[str | None] = mapped_column(String(80))
    captured_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    evidence: Mapped[dict] = mapped_column(JSONB, server_default=text("'{}'::jsonb"))


class Conversation(Base, TenantScoped):
    __tablename__ = "conversations"
    __table_args__ = (
        CheckConstraint(_in("status", ("open", "waiting_customer", "waiting_staff", "closed")), name="conversations_status"),
        CheckConstraint(_in("ai_mode", ("auto", "draft", "off")), name="conversations_ai_mode"),
    )
    contact_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("contacts.id", ondelete="CASCADE"), index=True)
    channel: Mapped[str] = mapped_column(String(20))
    status: Mapped[str] = mapped_column(String(20), server_default="open")
    assigned_user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))
    ai_mode: Mapped[str] = mapped_column(String(10), server_default="draft")
    last_inbound_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    topic: Mapped[str | None] = mapped_column(String(20))  # what it's about, for routing (ondra_core.routing.TOPICS)


class Message(Base, TenantScoped):
    __tablename__ = "messages"
    __table_args__ = (
        CheckConstraint(_in("direction", ("inbound", "outbound")), name="messages_direction"),
        CheckConstraint(_in("author_type", ("customer", "ai", "user", "system")), name="messages_author_type"),
        CheckConstraint(_in("status", ("queued", "sent", "delivered", "read", "failed", "received")), name="messages_status"),
        UniqueConstraint("tenant_id", "provider", "provider_message_id", name="messages_provider_id"),
    )
    conversation_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("conversations.id", ondelete="CASCADE"), index=True)
    direction: Mapped[str] = mapped_column(String(10))
    author_type: Mapped[str] = mapped_column(String(10))
    author_user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))
    body: Mapped[str | None] = mapped_column(Text)
    attachments: Mapped[list] = mapped_column(JSONB, server_default=text("'[]'::jsonb"))
    provider: Mapped[str | None] = mapped_column(String(40))
    provider_message_id: Mapped[str | None] = mapped_column(String(200))
    status: Mapped[str] = mapped_column(String(12), server_default="queued")
    is_draft: Mapped[bool] = mapped_column(Boolean, server_default=text("false"))


class Call(Base, TenantScoped):
    __tablename__ = "calls"
    conversation_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("conversations.id", ondelete="SET NULL"))
    provider_call_sid: Mapped[str | None] = mapped_column(String(200))
    direction: Mapped[str] = mapped_column(String(10))
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    duration_s: Mapped[int | None] = mapped_column(Integer)
    recording_url: Mapped[str | None] = mapped_column(Text)
    recording_consent: Mapped[bool] = mapped_column(Boolean, server_default=text("false"))
    transcript: Mapped[list] = mapped_column(JSONB, server_default=text("'[]'::jsonb"))
    summary: Mapped[str | None] = mapped_column(Text)
    sentiment: Mapped[str | None] = mapped_column(String(20))
    outcome: Mapped[str | None] = mapped_column(String(40))
    contact_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("contacts.id", ondelete="SET NULL"), index=True)
    from_number: Mapped[str | None] = mapped_column(String(32))
    to_number: Mapped[str | None] = mapped_column(String(32))
    # Who took it: ai, staff, owner (a VIP rang through), or missed.
    handled_by: Mapped[str | None] = mapped_column(String(10))
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    transferred_to_user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))
    # Per-turn timings from the voice agent (end of caller speech to first audio), for the latency report.
    metrics: Mapped[dict] = mapped_column(JSONB, server_default=text("'{}'::jsonb"))
    callback_done_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Deal(Base, TenantScoped):
    __tablename__ = "deals"
    __table_args__ = (CheckConstraint(_in("type", ("sales", "service")), name="deals_type"),)
    contact_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("contacts.id", ondelete="CASCADE"), index=True)
    type: Mapped[str] = mapped_column(String(10))
    stage: Mapped[str] = mapped_column(String(40), server_default="new")
    vehicle_of_interest: Mapped[dict] = mapped_column(JSONB, server_default=text("'{}'::jsonb"))
    budget_min: Mapped[float | None] = mapped_column(Numeric(12, 2))
    budget_max: Mapped[float | None] = mapped_column(Numeric(12, 2))
    currency: Mapped[str] = mapped_column(String(3), server_default="USD")
    destination: Mapped[str | None] = mapped_column(String(200))
    timeline: Mapped[str | None] = mapped_column(String(80))
    payment_method: Mapped[str | None] = mapped_column(String(40))
    owner_user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))
    source_channel: Mapped[str | None] = mapped_column(String(20))
    value_estimate: Mapped[float | None] = mapped_column(Numeric(12, 2))
    lost_reason: Mapped[str | None] = mapped_column(String(200))


class Vehicle(Base, TenantScoped):
    __tablename__ = "vehicles"
    __table_args__ = (
        CheckConstraint(_in("status", ("available", "hold", "sold")), name="vehicles_status"),
        UniqueConstraint("tenant_id", "stock_number", name="vehicles_stock_number"),
    )
    stock_number: Mapped[str] = mapped_column(String(40))
    vin: Mapped[str | None] = mapped_column(String(17))
    year: Mapped[int] = mapped_column(Integer)
    make: Mapped[str] = mapped_column(String(60))
    model: Mapped[str] = mapped_column(String(60))
    trim: Mapped[str | None] = mapped_column(String(80))
    price: Mapped[float | None] = mapped_column(Numeric(12, 2))
    mileage: Mapped[int | None] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(12), server_default="available")
    photos: Mapped[list[str]] = mapped_column(ARRAY(Text), server_default=text("'{}'"))
    source_feed: Mapped[str | None] = mapped_column(String(40))
    raw: Mapped[dict] = mapped_column(JSONB, server_default=text("'{}'::jsonb"))


class AppointmentType(Base, TenantScoped):
    __tablename__ = "appointment_types"
    name: Mapped[str] = mapped_column(String(120))
    description: Mapped[str | None] = mapped_column(Text)  # what the AI and staff see when choosing a type
    category: Mapped[str] = mapped_column(String(40))
    duration_min: Mapped[int] = mapped_column(Integer)
    buffer_min: Mapped[int] = mapped_column(Integer, server_default="0")
    eligible_roles: Mapped[list[str]] = mapped_column(ARRAY(Text), server_default=text("'{}'"))
    eligible_user_ids: Mapped[list[uuid.UUID]] = mapped_column(ARRAY(UUID(as_uuid=True)), server_default=text("'{}'"))
    required_resource_kinds: Mapped[list[str]] = mapped_column(ARRAY(Text), server_default=text("'{}'"))
    capacity: Mapped[int] = mapped_column(Integer, server_default="1")
    bookable_hours: Mapped[dict] = mapped_column(JSONB, server_default=text("'{}'::jsonb"))
    min_notice_min: Mapped[int] = mapped_column(Integer, server_default="60")
    max_days_ahead: Mapped[int] = mapped_column(Integer, server_default="30")
    required_fields: Mapped[list] = mapped_column(JSONB, server_default=text("'[]'::jsonb"))
    reminder_schedule: Mapped[list] = mapped_column(JSONB, server_default=text("'[]'::jsonb"))
    active: Mapped[bool] = mapped_column(Boolean, server_default=text("true"))


class Resource(Base, TenantScoped):
    __tablename__ = "resources"
    __table_args__ = (CheckConstraint(_in("kind", ("service_bay", "loaner", "demo_vehicle", "room")), name="resources_kind"),)
    kind: Mapped[str] = mapped_column(String(20))
    name: Mapped[str] = mapped_column(String(120))
    capacity: Mapped[int] = mapped_column(Integer, server_default="1")
    hours: Mapped[dict] = mapped_column(JSONB, server_default=text("'{}'::jsonb"))
    active: Mapped[bool] = mapped_column(Boolean, server_default=text("true"))


class Appointment(Base, TenantScoped):
    __tablename__ = "appointments"
    __table_args__ = (
        CheckConstraint(_in("status", ("booked", "confirmed", "showed", "no_show", "cancelled")), name="appointments_status"),
        CheckConstraint(_in("source", ("ai", "staff", "customer_link")), name="appointments_source"),
        Index("appointments_starts_at", "tenant_id", "starts_at"),
    )
    contact_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("contacts.id", ondelete="CASCADE"))
    deal_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("deals.id", ondelete="SET NULL"))
    appointment_type_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("appointment_types.id"))
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    ends_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    assigned_user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))
    resource_ids: Mapped[list[uuid.UUID]] = mapped_column(ARRAY(UUID(as_uuid=True)), server_default=text("'{}'"))
    vehicle_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("vehicles.id", ondelete="SET NULL"))
    vin: Mapped[str | None] = mapped_column(String(17))
    service_type: Mapped[str | None] = mapped_column(String(80))
    transport: Mapped[str | None] = mapped_column(String(40))
    status: Mapped[str] = mapped_column(String(12), server_default="booked")
    source: Mapped[str] = mapped_column(String(16))
    external_ref: Mapped[str | None] = mapped_column(String(200))
    # The person/bay is busy until here (end + the type's buffer). Overlaps on this range are refused by an
    # exclusion constraint, so two bookings can never take the same person or bay, even in a race.
    blocks_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    conversation_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("conversations.id", ondelete="SET NULL"))
    details: Mapped[dict] = mapped_column(JSONB, server_default=text("'{}'::jsonb"))  # loaner, notes, vehicle
    reminders_sent: Mapped[list] = mapped_column(JSONB, server_default=text("'[]'::jsonb"))


class AppointmentResource(Base, TenantScoped):
    """A bay, loaner or room held by an appointment. Its own overlap constraint keeps one resource from being
    double-booked; `active` turns off when the appointment is cancelled or moved."""

    __tablename__ = "appointment_resources"
    appointment_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("appointments.id", ondelete="CASCADE"), index=True)
    resource_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("resources.id", ondelete="CASCADE"))
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    blocks_until: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    active: Mapped[bool] = mapped_column(Boolean, server_default=text("true"))


class Task(Base, TenantScoped):
    __tablename__ = "tasks"
    __table_args__ = (
        CheckConstraint(_in("status", ("open", "in_progress", "done", "cancelled")), name="tasks_status"),
        CheckConstraint(_in("source", ("ai_handoff", "rule", "manual")), name="tasks_source"),
        CheckConstraint(_in("urgency", ("low", "normal", "high")), name="tasks_urgency"),
    )
    title: Mapped[str] = mapped_column(String(300))
    contact_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("contacts.id", ondelete="SET NULL"))
    deal_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("deals.id", ondelete="SET NULL"))
    conversation_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("conversations.id", ondelete="SET NULL"))
    assignee_user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))
    due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(12), server_default="open")
    source: Mapped[str] = mapped_column(String(12), server_default="manual")
    brief: Mapped[str | None] = mapped_column(Text)
    urgency: Mapped[str] = mapped_column(String(10), server_default="normal")
    escalated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class RoutingRule(Base, TenantScoped):
    __tablename__ = "routing_rules"
    name: Mapped[str] = mapped_column(String(120), server_default="")
    priority: Mapped[int] = mapped_column(Integer)
    conditions: Mapped[dict] = mapped_column(JSONB, server_default=text("'{}'::jsonb"))
    action: Mapped[dict] = mapped_column(JSONB, server_default=text("'{}'::jsonb"))
    active: Mapped[bool] = mapped_column(Boolean, server_default=text("true"))


class KnowledgeDoc(Base, TenantScoped):
    __tablename__ = "knowledge_docs"
    title: Mapped[str] = mapped_column(String(300))
    body: Mapped[str] = mapped_column(Text)
    category: Mapped[str | None] = mapped_column(String(80))
    embedding = mapped_column(Vector(1024), nullable=True)
    embedding_space: Mapped[str | None] = mapped_column(String(40))  # which embedder made it; see ondra_core.embeddings
    updated_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))


class KnowledgeGap(Base, TenantScoped):
    __tablename__ = "knowledge_gaps"
    __table_args__ = (CheckConstraint(_in("status", ("open", "answered", "ignored")), name="knowledge_gaps_status"),)
    question: Mapped[str] = mapped_column(Text)
    example_conversation_ids: Mapped[list[uuid.UUID]] = mapped_column(ARRAY(UUID(as_uuid=True)), server_default=text("'{}'"))
    occurrences: Mapped[int] = mapped_column(Integer, server_default="1")
    status: Mapped[str] = mapped_column(String(10), server_default="open")
    answer_doc_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("knowledge_docs.id", ondelete="SET NULL"))
    embedding = mapped_column(Vector(1024), nullable=True)  # so the same question in other words is one gap
    embedding_space: Mapped[str | None] = mapped_column(String(40))
    last_asked_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    asked: Mapped[str | None] = mapped_column(Text)  # a customer's own words, saved when they asked (never a VIP's)


class MessageRating(Base, TenantScoped):
    """A person's verdict on one of Ondra's replies (BUILD_PLAN.md §6.3a). One per message; the latest wins."""

    __tablename__ = "message_ratings"
    __table_args__ = (CheckConstraint(_in("rating", ("good", "wrong", "tone")), name="message_ratings_rating"),)
    message_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("messages.id", ondelete="CASCADE"), unique=True)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))
    rating: Mapped[str] = mapped_column(String(10))
    note: Mapped[str | None] = mapped_column(Text)


class Policy(Base, TenantScoped):
    __tablename__ = "policies"
    __table_args__ = (CheckConstraint(_in("price_disclosure", ("none", "listed", "range")), name="policies_price_disclosure"),)
    never_say: Mapped[list[str]] = mapped_column(ARRAY(Text), server_default=text("'{}'"))
    price_disclosure: Mapped[str] = mapped_column(String(10), server_default="listed")
    handoff_triggers: Mapped[list[str]] = mapped_column(ARRAY(Text), server_default=text("'{}'"))
    draft_mode: Mapped[bool] = mapped_column(Boolean, server_default=text("true"))
    quiet_hours: Mapped[dict] = mapped_column(JSONB, server_default=text("'{}'::jsonb"))


class MessageTemplate(Base, TenantScoped):
    __tablename__ = "message_templates"
    channel: Mapped[str] = mapped_column(String(20))
    provider_template_name: Mapped[str | None] = mapped_column(String(200))
    language: Mapped[str] = mapped_column(String(20), server_default="en_US")
    category: Mapped[str | None] = mapped_column(String(40))
    body: Mapped[str] = mapped_column(Text)
    variables: Mapped[list] = mapped_column(JSONB, server_default=text("'[]'::jsonb"))
    approval_status: Mapped[str] = mapped_column(String(20), server_default="draft")


class FollowUpSequence(Base, TenantScoped):
    __tablename__ = "follow_up_sequences"
    name: Mapped[str] = mapped_column(String(200))
    # Each step: {"after_hours": 24, "write": "ondra" | "text", "text": "...", "require_approval": true}
    steps: Mapped[list] = mapped_column(JSONB, server_default=text("'[]'::jsonb"))
    active: Mapped[bool] = mapped_column(Boolean, server_default=text("true"))
    topics: Mapped[list[str]] = mapped_column(ARRAY(Text), server_default=text("'{}'"))  # empty: any conversation


class FollowUp(Base, TenantScoped):
    """One customer's next step in a sequence. A new row per step; ended rows say why (`reason`)."""

    __tablename__ = "follow_ups"
    __table_args__ = (CheckConstraint(_in("status", ("scheduled", "awaiting_approval", "sending", "sent", "cancelled",
                                                     "needs_person")), name="follow_ups_status"),)
    sequence_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("follow_up_sequences.id", ondelete="CASCADE"))
    conversation_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("conversations.id", ondelete="CASCADE"), index=True)
    contact_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("contacts.id", ondelete="CASCADE"), index=True)
    step: Mapped[int] = mapped_column(Integer)
    due_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(20), server_default="scheduled")
    reason: Mapped[str | None] = mapped_column(String(60))
    message_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("messages.id", ondelete="SET NULL"))
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Integration(Base, TenantScoped):
    __tablename__ = "integrations"
    __table_args__ = (
        CheckConstraint(
            _in("kind", ("dms", "crm_adf", "inventory_feed", "calendar", "whatsapp", "twilio", "telnyx", "email")),
            name="integrations_kind",
        ),
    )
    kind: Mapped[str] = mapped_column(String(20))
    config: Mapped[dict] = mapped_column(JSONB, server_default=text("'{}'::jsonb"))
    credentials_encrypted: Mapped[bytes | None] = mapped_column()  # ciphertext only; see ENCRYPTION_KEY_ID
    status: Mapped[str] = mapped_column(String(20), server_default="disconnected")
    last_sync_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class ChannelAddress(Base, TenantScoped):
    """The dealer's own numbers and addresses that customers write to. An inbound webhook names the address it was
    sent to; this is how Ondra knows which dealer it belongs to (before any tenant is set, via the SECURITY
    DEFINER function `channel_find_tenant`). An address belongs to exactly one dealer."""

    __tablename__ = "channel_addresses"
    __table_args__ = (UniqueConstraint("channel", "address", name="channel_addresses_unique"),)
    channel: Mapped[str] = mapped_column(String(20))  # sms | whatsapp | email
    address: Mapped[str] = mapped_column(String(320))  # E.164 or lowercased email
    provider: Mapped[str] = mapped_column(String(40))  # mock | twilio | whatsapp_cloud | postmark
    active: Mapped[bool] = mapped_column(Boolean, server_default=text("true"))


class Job(Base, TenantScoped):
    """Durable background work (the AI turn, escalation sweeps). Claimed by workers with SKIP LOCKED through the
    SECURITY DEFINER function `jobs_claim`; everything else about a job happens inside its tenant's session."""

    __tablename__ = "jobs"
    __table_args__ = (
        CheckConstraint(_in("status", ("queued", "running", "done", "failed")), name="jobs_status"),
        Index("jobs_ready", "status", "run_at"),
    )
    kind: Mapped[str] = mapped_column(String(40))
    payload: Mapped[dict] = mapped_column(JSONB, server_default=text("'{}'::jsonb"))
    status: Mapped[str] = mapped_column(String(10), server_default="queued")
    run_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    attempts: Mapped[int] = mapped_column(Integer, server_default="0")
    max_attempts: Mapped[int] = mapped_column(Integer, server_default="5")
    locked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_error: Mapped[str | None] = mapped_column(Text)


class Event(Base, TenantScoped):
    __tablename__ = "events"
    __table_args__ = (Index("events_type_time", "tenant_id", "type", "occurred_at"),)
    type: Mapped[str] = mapped_column(String(80))
    payload: Mapped[dict] = mapped_column(JSONB, server_default=text("'{}'::jsonb"))
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class AuditLog(Base, TenantScoped):
    __tablename__ = "audit_log"
    __table_args__ = (CheckConstraint(_in("actor_type", ("user", "ai", "system")), name="audit_log_actor_type"),)
    actor_type: Mapped[str] = mapped_column(String(10))
    actor_user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))
    action: Mapped[str] = mapped_column(String(80))
    resource: Mapped[str] = mapped_column(String(200))
    before: Mapped[dict | None] = mapped_column(JSONB)
    after: Mapped[dict | None] = mapped_column(JSONB)
    ip: Mapped[str | None] = mapped_column(String(64))


# Every table that holds dealer data. The migration enables and forces RLS on each, and a test asserts
# that no table with a tenant_id column is missing from this list.
TENANT_TABLES = tuple(t.name for t in Base.metadata.sorted_tables if "tenant_id" in t.c)
