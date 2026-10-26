"""Class bookings for a gym (Domicio Rondón Boxing Gym).

Booking is by request: the student asks for a class, the gym confirms by hand. Membership
payment happens outside Sabi, so nothing here handles money.
"""
from datetime import datetime

from sqlalchemy import DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from .models import Base, utcnow

REQUEST_STATUSES = ("solicitada", "confirmada", "rechazada")


class GymProfile(Base):
    """One row: what Sabi may say about the gym. Empty fields are never invented."""
    __tablename__ = "gym_profile"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200), default="Domicio Rondón Boxing Gym")
    address: Mapped[str] = mapped_column(String(300), default="")
    classes_text: Mapped[str] = mapped_column(Text, default="")    # e.g. "Boxeo recreativo, competitivo, niños"
    schedule_text: Mapped[str] = mapped_column(Text, default="")   # e.g. "Lun a Vie 6:00-8:00 y 17:00-20:00"
    membership_text: Mapped[str] = mapped_column(Text, default="")  # price/conditions as the gym states them
    contact: Mapped[str] = mapped_column(String(200), default="")
    owner_phone: Mapped[str] = mapped_column(String(30), default="")  # gets a WhatsApp for each request
    # Google Calendar id the gym shared with Sabi's service account (nullable: added after launch).
    calendar_id: Mapped[str | None] = mapped_column(String(300), nullable=True)


class ClassRequest(Base):
    __tablename__ = "gym_class_requests"

    id: Mapped[int] = mapped_column(primary_key=True)
    phone: Mapped[str] = mapped_column(String(30), index=True)
    student_name: Mapped[str] = mapped_column(String(120))
    level: Mapped[str] = mapped_column(String(40), default="")
    preferred: Mapped[str] = mapped_column(String(200), default="")  # day/time as the student wrote it
    status: Mapped[str] = mapped_column(String(12), default="solicitada", index=True)
    gym_note: Mapped[str] = mapped_column(Text, default="")  # confirmed day/time or reason, sent to the student
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, index=True)
    reviewed_by: Mapped[str] = mapped_column(String(200), default="")
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    # Confirmed class slot (naive UTC) and its Google Calendar event, when connected.
    starts_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    duration_minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    calendar_event_id: Mapped[str | None] = mapped_column(String(200), nullable=True)
    calendar_link: Mapped[str | None] = mapped_column(String(500), nullable=True)
