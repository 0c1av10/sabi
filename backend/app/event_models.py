"""Tables for the events assistant (FC Producciones demo).

Money is stored as integer minor units (cents) plus an ISO currency code; amounts in
different currencies are never added or converted here.
"""
from datetime import datetime

from sqlalchemy import (Boolean, DateTime, ForeignKey, Integer, String, Text)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .models import Base, utcnow

EVENT_STATUSES = ("borrador", "publicado", "cancelado", "finalizado")
ZONE_AVAILABILITY = ("disponible", "agotado", "por_confirmar")
CURRENCIES = ("USD", "EUR", "VES")
ACTIVITY_KINDS = ("interest", "selection", "click", "payment_reported", "human_request")
PURCHASE_STATUSES = ("reported", "confirmed", "rejected")


class Event(Base):
    __tablename__ = "events"

    id: Mapped[int] = mapped_column(primary_key=True)
    slug: Mapped[str] = mapped_column(String(120), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(200))
    artist: Mapped[str] = mapped_column(String(200), default="")
    city: Mapped[str] = mapped_column(String(100), index=True)
    venue: Mapped[str] = mapped_column(String(200), default="")
    # Stored as naive UTC; `timezone` is the IANA zone used to display it.
    starts_at: Mapped[datetime] = mapped_column(DateTime)
    timezone: Mapped[str] = mapped_column(String(60), default="America/Caracas")
    description: Mapped[str] = mapped_column(Text, default="")
    image_url: Mapped[str] = mapped_column(String(500), default="")
    status: Mapped[str] = mapped_column(String(20), default="borrador", index=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    # Verified official purchase link (empty = purchase disabled). Never built by us.
    purchase_url: Mapped[str] = mapped_column(String(500), default="")
    is_demo: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)

    zones: Mapped[list["EventZone"]] = relationship(
        back_populates="event", cascade="all, delete-orphan", order_by="EventZone.id")


class EventZone(Base):
    __tablename__ = "event_zones"

    id: Mapped[int] = mapped_column(primary_key=True)
    event_id: Mapped[int] = mapped_column(ForeignKey("events.id"), index=True)
    name: Mapped[str] = mapped_column(String(120))
    price_minor: Mapped[int] = mapped_column(Integer)
    currency: Mapped[str] = mapped_column(String(3), default="USD")
    availability: Mapped[str] = mapped_column(String(20), default="por_confirmar")
    verified_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    event: Mapped[Event] = relationship(back_populates="zones")


class EventSession(Base):
    """One chat conversation with Sabi (web today; WhatsApp later via an adapter)."""
    __tablename__ = "event_sessions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    channel: Mapped[str] = mapped_column(String(20), default="web")
    state_json: Mapped[str] = mapped_column(Text, default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)


class EventMessage(Base):
    __tablename__ = "event_messages"

    id: Mapped[int] = mapped_column(primary_key=True)
    session_id: Mapped[str] = mapped_column(ForeignKey("event_sessions.id"), index=True)
    role: Mapped[str] = mapped_column(String(10))  # user | assistant
    body: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, index=True)


class EventSelection(Base):
    """A prepared selection. It is NOT a reservation."""
    __tablename__ = "event_selections"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    session_id: Mapped[str] = mapped_column(ForeignKey("event_sessions.id"), index=True)
    event_id: Mapped[int] = mapped_column(ForeignKey("events.id"), index=True)
    zone_id: Mapped[int] = mapped_column(ForeignKey("event_zones.id"))
    quantity: Mapped[int] = mapped_column(Integer)
    unit_price_minor: Mapped[int] = mapped_column(Integer)
    subtotal_minor: Mapped[int] = mapped_column(Integer)
    currency: Mapped[str] = mapped_column(String(3))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class EventActivity(Base):
    """Analytics: interest | selection | click | payment_reported | human_request."""
    __tablename__ = "event_activity"

    id: Mapped[int] = mapped_column(primary_key=True)
    session_id: Mapped[str | None] = mapped_column(ForeignKey("event_sessions.id"), nullable=True, index=True)
    event_id: Mapped[int | None] = mapped_column(ForeignKey("events.id"), nullable=True, index=True)
    zone_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    selection_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    kind: Mapped[str] = mapped_column(String(20), index=True)
    detail: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, index=True)


class EventPurchaseReport(Base):
    """A user-reported payment ("ya pagué"). Only an admin can mark it confirmed."""
    __tablename__ = "event_purchase_reports"

    id: Mapped[int] = mapped_column(primary_key=True)
    session_id: Mapped[str] = mapped_column(ForeignKey("event_sessions.id"), index=True)
    selection_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    event_id: Mapped[int | None] = mapped_column(ForeignKey("events.id"), nullable=True, index=True)
    user_reference: Mapped[str] = mapped_column(String(160), default="")
    status: Mapped[str] = mapped_column(String(12), default="reported", index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    # Filled only by an authenticated admin:
    reviewed_by: Mapped[str] = mapped_column(String(200), default="")
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    confirmed_reference: Mapped[str] = mapped_column(String(160), default="")
    confirmed_amount_minor: Mapped[int | None] = mapped_column(Integer, nullable=True)
    confirmed_currency: Mapped[str] = mapped_column(String(3), default="")
    note: Mapped[str] = mapped_column(Text, default="")


class EventLoginFailure(Base):
    """Failed admin logins, kept in the database so throttling survives serverless restarts."""
    __tablename__ = "event_login_failures"

    id: Mapped[int] = mapped_column(primary_key=True)
    key: Mapped[str] = mapped_column(String(80), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, index=True)
