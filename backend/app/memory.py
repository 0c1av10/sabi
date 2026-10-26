"""Sabi's memory of who it is talking to, shared by every channel (restaurants, tickets, classes).

One row per WhatsApp number: the name to address them by and the last thing Sabi helped with.
A name the person gives in the chat always wins over the WhatsApp profile name. Anyone can ask
Sabi to forget them ("olvídame"), which deletes the row.
"""
import re
import unicodedata
from datetime import datetime

from sqlalchemy import DateTime, String, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Mapped, mapped_column

from .models import Base, utcnow
from .whatsapp import digits


class Contact(Base):
    __tablename__ = "contacts"

    phone: Mapped[str] = mapped_column(String(30), primary_key=True)
    name: Mapped[str | None] = mapped_column(String(60), nullable=True)
    name_source: Mapped[str | None] = mapped_column(String(10), nullable=True)  # "user" | "profile"
    last_topic: Mapped[str | None] = mapped_column(String(80), nullable=True)
    first_seen: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    last_seen: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


_NOT_NAMES = {"principiante", "intermedio", "avanzado", "nuevo", "nueva", "cliente", "alumno", "alumna", "el", "la",
              "un", "una", "yo", "tu", "de", "del", "que", "quien", "usuario", "persona", "amigo", "amiga",
              "hola", "buenas", "ok", "si", "no", "sabi", "boxeador", "estudiante", "mama", "papa"}
_INTRO = re.compile(
    r"\b(?:me\s+llamo|mi\s+nombre\s+es|ll[aá]mame|dime|soy)\s+([A-Za-zÁÉÍÓÚÑáéíóúñ]{2,20}(?:\s+[A-Za-zÁÉÍÓÚÑáéíóúñ]{2,20}){0,2})",
    re.I)
FORGET = re.compile(r"\b(olv[ií]dame|olvida\s+mi\s+nombre|borra\s+mis\s+datos|no\s+me\s+recuerdes)\b", re.I)


def _plain(text: str) -> str:
    nfkd = unicodedata.normalize("NFKD", text or "")
    return "".join(c for c in nfkd if not unicodedata.combining(c)).lower()


def clean_name(raw: str | None) -> str:
    """A presentable name from free text or a WhatsApp profile: letters only, capitalised."""
    words = re.findall(r"[A-Za-zÁÉÍÓÚÑáéíóúñ]{2,20}", raw or "")[:3]
    if not words or _plain(words[0]) in _NOT_NAMES:
        return ""
    return " ".join(w[:1].upper() + w[1:].lower() for w in words)


def extract_name(body: str) -> str:
    m = _INTRO.search(body or "")
    if not m:
        return ""
    words = m.group(1).split()
    kept = []
    for w in words:
        if _plain(w) in _NOT_NAMES or _plain(w) in {"y", "quiero", "busco", "necesito", "para", "con", "de"}:
            break
        kept.append(w)
    return clean_name(" ".join(kept))


def first_name(name: str | None) -> str:
    return (name or "").split()[0] if name else ""


async def get(db: AsyncSession, phone: str) -> Contact | None:
    return await db.get(Contact, digits(phone)) if digits(phone) else None


async def note(db: AsyncSession, phone: str, body: str = "", profile_name: str = "",
               topic: str = "") -> Contact | None:
    """Update memory from one inbound message. Never raises into the chat flow."""
    key = digits(phone)
    if not key:
        return None
    try:
        c = await db.get(Contact, key)
        if not c:
            c = Contact(phone=key)
            db.add(c)
        said = extract_name(body)
        if said:
            c.name, c.name_source = said, "user"
        elif not c.name:
            profile = clean_name(profile_name)
            if profile:
                c.name, c.name_source = profile, "profile"
        if topic:
            c.last_topic = topic[:80]
        c.last_seen = utcnow()
        await db.commit()
        return c
    except Exception:  # noqa: BLE001
        await db.rollback()
        return None


async def set_topic(db: AsyncSession, phone: str, topic: str) -> None:
    await note(db, phone, topic=topic)


async def set_name(db: AsyncSession, phone: str, name: str) -> None:
    clean = clean_name(name)
    if not clean:
        return
    c = await get(db, phone) or Contact(phone=digits(phone))
    c.name, c.name_source, c.last_seen = clean, "user", utcnow()
    db.add(c)
    await db.commit()


async def forget(db: AsyncSession, phone: str) -> None:
    c = await get(db, phone)
    if c:
        await db.delete(c)
        await db.commit()
