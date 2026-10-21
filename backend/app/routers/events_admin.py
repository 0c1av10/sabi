"""Admin API for the events assistant. Only an authenticated admin can edit the catalog or
confirm a purchase; neither the end user nor the model can."""
import csv
import hashlib
import hmac
import io
import re
import unicodedata
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Literal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import distinct, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from ..config import settings
from ..db import get_db
from ..event_models import (Event, EventActivity, EventLoginFailure, EventMessage,
                            EventPurchaseReport, EventSelection, EventSession, EventZone)
from ..event_service import (fmt_minor, to_minor, validate_purchase_url, zone_needs_verification)
from ..models import utcnow

router = APIRouter(prefix="/api/events/admin", tags=["events-admin"])

ADMIN_COOKIE = "sabi_events_admin"
SESSION_HOURS = 12
MAX_FAILURES = 5
FAILURE_WINDOW = timedelta(minutes=15)


# ----------------------------------------------------------------------------- auth

def _serializer() -> URLSafeTimedSerializer:
    return URLSafeTimedSerializer(settings.session_secret, salt="sabi-events-admin")


def admin_emails() -> set[str]:
    return {e.strip().lower() for e in settings.events_admin_emails.split(",") if e.strip()}


def admin_enabled() -> bool:
    return bool(admin_emails() and settings.events_admin_password)


async def current_admin(request: Request) -> str:
    """Returns the admin's email or raises 401. Re-checked against the allowlist each time."""
    if not admin_enabled():
        raise HTTPException(503, "El panel de administración no está configurado")
    token = request.cookies.get(ADMIN_COOKIE, "")
    try:
        email = _serializer().loads(token, max_age=SESSION_HOURS * 3600).get("adm", "")
    except (BadSignature, SignatureExpired):
        raise HTTPException(401, "No autenticado")
    if email not in admin_emails():
        raise HTTPException(401, "No autenticado")
    return email


def _client_key(request: Request) -> str:
    fwd = request.headers.get("x-forwarded-for", "")
    ip = fwd.split(",")[0].strip() if fwd else (request.client.host if request.client else "")
    return hashlib.sha256(ip.encode()).hexdigest()[:24]


class LoginIn(BaseModel):
    email: str = Field(..., max_length=200)
    password: str = Field(..., max_length=200)


@router.post("/login")
async def login(data: LoginIn, request: Request, response: Response, db: AsyncSession = Depends(get_db)):
    if not admin_enabled():
        raise HTTPException(503, "El panel de administración no está configurado")
    email = data.email.strip().lower()
    keys = ["i:" + _client_key(request), "e:" + hashlib.sha256(email.encode()).hexdigest()[:24]]
    since = utcnow() - FAILURE_WINDOW
    per_key = (await db.execute(
        select(EventLoginFailure.key, func.count(EventLoginFailure.id))
        .where(EventLoginFailure.key.in_(keys), EventLoginFailure.created_at >= since)
        .group_by(EventLoginFailure.key))).all()
    if max((n for _, n in per_key), default=0) >= MAX_FAILURES:  # per IP or per email
        raise HTTPException(429, "Demasiados intentos. Espera unos minutos.")
    pass_ok = hmac.compare_digest(data.password.encode(), settings.events_admin_password.encode())
    mail_ok = email in admin_emails()
    if not (pass_ok and mail_ok):
        for k in keys:
            db.add(EventLoginFailure(key=k))
        await db.commit()
        raise HTTPException(401, "Correo o contraseña incorrectos")
    secure = request.url.scheme == "https" or request.headers.get("x-forwarded-proto") == "https"
    response.set_cookie(ADMIN_COOKIE, _serializer().dumps({"adm": email}), httponly=True,
                        samesite="lax", secure=secure, max_age=SESSION_HOURS * 3600, path="/")
    return {"email": email}


@router.post("/logout")
async def logout(response: Response):
    response.delete_cookie(ADMIN_COOKIE, path="/")
    return {"ok": True}


@router.get("/me")
async def me(admin: str = Depends(current_admin)):
    return {"email": admin}


# -------------------------------------------------------------------------- schemas

Currency = Literal["USD", "EUR", "VES"]
Availability = Literal["disponible", "agotado", "por_confirmar"]
EventStatus = Literal["borrador", "publicado", "cancelado", "finalizado"]


def slugify(text: str) -> str:
    nfkd = unicodedata.normalize("NFKD", text)
    ascii_text = "".join(c for c in nfkd if not unicodedata.combining(c)).lower()
    return re.sub(r"[^a-z0-9]+", "-", ascii_text).strip("-")[:100] or "evento"


class ZoneIn(BaseModel):
    name: str = Field(..., min_length=1, max_length=120)
    price: Decimal = Field(..., gt=0, lt=Decimal("10000000"))
    currency: Currency = "USD"
    availability: Availability = "por_confirmar"
    mark_verified: bool = False  # stamps "last verified" = now

    @field_validator("price")
    @classmethod
    def two_decimals(cls, v: Decimal) -> Decimal:
        if v.as_tuple().exponent < -2:
            raise ValueError("El precio admite máximo 2 decimales")
        return v


class EventIn(BaseModel):
    name: str = Field(..., min_length=2, max_length=200)
    slug: str | None = Field(None, pattern=r"^[a-z0-9-]{3,120}$")
    artist: str = Field("", max_length=200)
    city: str = Field(..., min_length=2, max_length=100)
    venue: str = Field("", max_length=200)
    starts_at: datetime
    timezone: str = Field("America/Caracas", max_length=60)
    description: str = Field("", max_length=4000)
    image_url: str = Field("", max_length=500)
    status: EventStatus = "borrador"
    active: bool = True
    purchase_url: str = Field("", max_length=500)
    is_demo: bool = False

    @field_validator("timezone")
    @classmethod
    def valid_tz(cls, v: str) -> str:
        try:
            ZoneInfo(v)
        except (ZoneInfoNotFoundError, ValueError):
            raise ValueError("Zona horaria inválida (ej. America/Caracas)")
        return v

    @field_validator("image_url")
    @classmethod
    def image_https(cls, v: str) -> str:
        if v and not v.startswith("https://"):
            raise ValueError("La imagen debe ser una URL https://")
        return v


def _to_utc_naive(dt: datetime, tz_name: str) -> datetime:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=ZoneInfo(tz_name))
    return dt.astimezone(timezone.utc).replace(tzinfo=None)


def _clean_url(url: str, is_demo: bool) -> str:
    try:
        clean = validate_purchase_url(url)
    except ValueError as exc:
        raise HTTPException(422, str(exc))
    if is_demo and clean:
        raise HTTPException(422, "Los eventos de demostración no pueden tener enlace de compra")
    return clean


def zone_admin(z: EventZone) -> dict:
    return {"id": z.id, "name": z.name, "price": f"{Decimal(z.price_minor) / 100:.2f}",
            "price_label": fmt_minor(z.price_minor, z.currency), "currency": z.currency,
            "availability": z.availability,
            "verified_at": z.verified_at.isoformat() if z.verified_at else None,
            "needs_verification": zone_needs_verification(z)}


def event_admin(e: Event) -> dict:
    return {"id": e.id, "slug": e.slug, "name": e.name, "artist": e.artist, "city": e.city,
            "venue": e.venue, "starts_at": e.starts_at.replace(tzinfo=timezone.utc).isoformat(),
            "timezone": e.timezone, "description": e.description, "image_url": e.image_url,
            "status": e.status, "active": e.active, "purchase_url": e.purchase_url,
            "is_demo": e.is_demo, "updated_at": e.updated_at.isoformat(),
            "zones": [zone_admin(z) for z in e.zones]}


async def _event_or_404(db: AsyncSession, event_id: int) -> Event:
    ev = (await db.execute(select(Event).where(Event.id == event_id)
                           .options(selectinload(Event.zones)))).scalar_one_or_none()
    if not ev:
        raise HTTPException(404, "Evento no encontrado")
    return ev


async def _unique_slug(db: AsyncSession, base: str, exclude_id: int | None = None) -> str:
    slug, n = base, 2
    while True:
        q = select(Event.id).where(Event.slug == slug)
        row = (await db.execute(q)).first()
        if not row or row[0] == exclude_id:
            return slug
        slug, n = f"{base}-{n}", n + 1


# ------------------------------------------------------------------- events & zones

@router.get("/events")
async def list_events(admin: str = Depends(current_admin), db: AsyncSession = Depends(get_db)):
    events = (await db.execute(select(Event).options(selectinload(Event.zones))
                               .order_by(Event.starts_at.desc()))).scalars().all()
    return [event_admin(e) for e in events]


@router.post("/events", status_code=201)
async def create_event(data: EventIn, admin: str = Depends(current_admin), db: AsyncSession = Depends(get_db)):
    url = _clean_url(data.purchase_url, data.is_demo)
    slug = await _unique_slug(db, data.slug or slugify(data.name))
    ev = Event(slug=slug, name=data.name.strip(), artist=data.artist.strip(), city=data.city.strip(),
               venue=data.venue.strip(), starts_at=_to_utc_naive(data.starts_at, data.timezone),
               timezone=data.timezone, description=data.description, image_url=data.image_url,
               status=data.status, active=data.active, purchase_url=url, is_demo=data.is_demo)
    db.add(ev)
    await db.commit()
    return event_admin(await _event_or_404(db, ev.id))


@router.put("/events/{event_id}")
async def update_event(event_id: int, data: EventIn, admin: str = Depends(current_admin),
                       db: AsyncSession = Depends(get_db)):
    ev = await _event_or_404(db, event_id)
    ev.purchase_url = _clean_url(data.purchase_url, data.is_demo)
    if data.slug:
        ev.slug = await _unique_slug(db, data.slug, exclude_id=ev.id)
    ev.name, ev.artist, ev.city = data.name.strip(), data.artist.strip(), data.city.strip()
    ev.venue, ev.timezone = data.venue.strip(), data.timezone
    ev.starts_at = _to_utc_naive(data.starts_at, data.timezone)
    ev.description, ev.image_url = data.description, data.image_url
    ev.status, ev.active, ev.is_demo = data.status, data.active, data.is_demo
    ev.updated_at = utcnow()
    await db.commit()
    return event_admin(await _event_or_404(db, ev.id))


@router.post("/sync")
async def sync_catalog(admin: str = Depends(current_admin), db: AsyncSession = Depends(get_db)):
    """Pull events, zones, prices and availability from the official platform now."""
    from .. import event_sync
    try:
        return await event_sync.sync(db)
    except Exception as exc:
        raise HTTPException(502, f"No se pudo leer la fuente: {type(exc).__name__}")


@router.post("/events/{event_id}/active")
async def set_active(event_id: int, body: dict, admin: str = Depends(current_admin),
                     db: AsyncSession = Depends(get_db)):
    """Deactivate/reactivate without deleting history."""
    ev = await _event_or_404(db, event_id)
    ev.active = bool(body.get("active"))
    ev.updated_at = utcnow()
    await db.commit()
    return event_admin(ev)


@router.post("/events/{event_id}/zones", status_code=201)
async def add_zone(event_id: int, data: ZoneIn, admin: str = Depends(current_admin),
                   db: AsyncSession = Depends(get_db)):
    ev = await _event_or_404(db, event_id)
    ev.zones.append(EventZone(name=data.name.strip(), price_minor=to_minor(data.price),
                              currency=data.currency, availability=data.availability,
                              verified_at=utcnow() if data.mark_verified else None))
    ev.updated_at = utcnow()
    await db.commit()
    return event_admin(await _event_or_404(db, event_id))


@router.put("/zones/{zone_id}")
async def update_zone(zone_id: int, data: ZoneIn, admin: str = Depends(current_admin),
                      db: AsyncSession = Depends(get_db)):
    zone = await db.get(EventZone, zone_id)
    if not zone:
        raise HTTPException(404, "Zona no encontrada")
    zone.name, zone.currency, zone.availability = data.name.strip(), data.currency, data.availability
    zone.price_minor = to_minor(data.price)
    if data.mark_verified:
        zone.verified_at = utcnow()
    ev = await db.get(Event, zone.event_id)
    ev.updated_at = utcnow()
    await db.commit()
    return event_admin(await _event_or_404(db, zone.event_id))


# --------------------------------------------------------------- tracking & review

def _names(events: dict[int, Event], zones: dict[int, EventZone], row) -> dict:
    return {"event": events[row.event_id].name if row.event_id in events else "",
            "zone": zones[row.zone_id].name if getattr(row, "zone_id", None) in zones else ""}


async def _lookup(db: AsyncSession) -> tuple[dict[int, Event], dict[int, EventZone]]:
    events = {e.id: e for e in (await db.execute(select(Event))).scalars().all()}
    zones = {z.id: z for z in (await db.execute(select(EventZone))).scalars().all()}
    return events, zones


async def _activity_rows(db: AsyncSession, kind: str | None, limit: int) -> list[dict]:
    q = select(EventActivity).order_by(EventActivity.id.desc()).limit(limit)
    if kind:
        q = q.where(EventActivity.kind == kind)
    rows = (await db.execute(q)).scalars().all()
    events, zones = await _lookup(db)
    return [{"id": r.id, "kind": r.kind, "created_at": r.created_at.isoformat(),
             "session_id": r.session_id or "", "selection_id": r.selection_id or "",
             "detail": r.detail, **_names(events, zones, r)} for r in rows]


@router.get("/activity")
async def activity(kind: str | None = None, limit: int = 200, admin: str = Depends(current_admin),
                   db: AsyncSession = Depends(get_db)):
    return await _activity_rows(db, kind, max(1, min(limit, 1000)))


async def _selection_rows(db: AsyncSession, limit: int) -> list[dict]:
    rows = (await db.execute(select(EventSelection).order_by(EventSelection.created_at.desc())
                             .limit(limit))).scalars().all()
    events, zones = await _lookup(db)
    return [{"id": r.id, "created_at": r.created_at.isoformat(), "session_id": r.session_id,
             "quantity": r.quantity, "unit_price": fmt_minor(r.unit_price_minor, r.currency),
             "subtotal": fmt_minor(r.subtotal_minor, r.currency), "currency": r.currency,
             "note": "subtotal orientativo, no es una venta", **_names(events, zones, r)} for r in rows]


@router.get("/selections")
async def selections(limit: int = 200, admin: str = Depends(current_admin), db: AsyncSession = Depends(get_db)):
    return await _selection_rows(db, max(1, min(limit, 1000)))


async def _purchase_rows(db: AsyncSession, status: str | None, limit: int,
                         report_id: int | None = None) -> list[dict]:
    q = select(EventPurchaseReport).order_by(EventPurchaseReport.id.desc()).limit(limit)
    if status:
        q = q.where(EventPurchaseReport.status == status)
    if report_id is not None:
        q = q.where(EventPurchaseReport.id == report_id)
    rows = (await db.execute(q)).scalars().all()
    events, zones = await _lookup(db)
    sels = {s.id: s for s in (await db.execute(select(EventSelection))).scalars().all()}
    out = []
    for r in rows:
        sel = sels.get(r.selection_id or "")
        out.append({
            "id": r.id, "status": r.status, "created_at": r.created_at.isoformat(),
            "session_id": r.session_id, "user_reference": r.user_reference,
            "event": events[r.event_id].name if r.event_id in events else "",
            "zone": zones[sel.zone_id].name if sel and sel.zone_id in zones else "",
            "quantity": sel.quantity if sel else None,
            "estimated_subtotal": fmt_minor(sel.subtotal_minor, sel.currency) if sel else "",
            "reviewed_by": r.reviewed_by, "reviewed_at": r.reviewed_at.isoformat() if r.reviewed_at else "",
            "confirmed_reference": r.confirmed_reference,
            "confirmed_amount": fmt_minor(r.confirmed_amount_minor, r.confirmed_currency)
            if r.confirmed_amount_minor is not None else "",
            "note": r.note, "attribution": "manual" if r.status == "confirmed" else ""})
    return out


@router.get("/purchases")
async def purchases(status: str | None = None, limit: int = 200, admin: str = Depends(current_admin),
                    db: AsyncSession = Depends(get_db)):
    return await _purchase_rows(db, status, max(1, min(limit, 1000)))


class ConfirmIn(BaseModel):
    reference: str = Field(..., min_length=1, max_length=160)
    amount: Decimal = Field(..., gt=0, lt=Decimal("100000000"))
    currency: Currency
    note: str = Field("", max_length=500)

    @field_validator("amount")
    @classmethod
    def two_decimals(cls, v: Decimal) -> Decimal:
        if v.as_tuple().exponent < -2:
            raise ValueError("El importe admite máximo 2 decimales")
        return v


class RejectIn(BaseModel):
    note: str = Field("", max_length=500)


@router.post("/purchases/{report_id}/confirm")
async def confirm_purchase(report_id: int, data: ConfirmIn, admin: str = Depends(current_admin),
                           db: AsyncSession = Depends(get_db)):
    report = await db.get(EventPurchaseReport, report_id)
    if not report:
        raise HTTPException(404, "Reporte no encontrado")
    if report.status != "reported":
        raise HTTPException(409, "Este reporte ya fue revisado")
    report.status = "confirmed"
    report.reviewed_by = admin  # identity comes from the signed session, never from the body
    report.reviewed_at = utcnow()
    report.confirmed_reference = data.reference.strip()
    report.confirmed_amount_minor = to_minor(data.amount)
    report.confirmed_currency = data.currency
    report.note = data.note
    await db.commit()
    return (await _purchase_rows(db, None, 1, report_id))[0]


@router.post("/purchases/{report_id}/reject")
async def reject_purchase(report_id: int, data: RejectIn, admin: str = Depends(current_admin),
                          db: AsyncSession = Depends(get_db)):
    report = await db.get(EventPurchaseReport, report_id)
    if not report:
        raise HTTPException(404, "Reporte no encontrado")
    if report.status != "reported":
        raise HTTPException(409, "Este reporte ya fue revisado")
    report.status, report.reviewed_by, report.reviewed_at, report.note = (
        "rejected", admin, utcnow(), data.note)
    await db.commit()
    return {"ok": True}


@router.get("/sessions")
async def sessions(limit: int = 100, admin: str = Depends(current_admin), db: AsyncSession = Depends(get_db)):
    limit = max(1, min(limit, 500))
    rows = (await db.execute(select(EventSession).order_by(EventSession.updated_at.desc())
                             .limit(limit))).scalars().all()
    msg_counts = dict((await db.execute(select(EventMessage.session_id, func.count(EventMessage.id))
                                        .group_by(EventMessage.session_id))).all())
    kinds: dict[str, set[str]] = {}
    for sid, kind in (await db.execute(select(EventActivity.session_id, EventActivity.kind).distinct()
                                       .where(EventActivity.session_id.is_not(None)))).all():
        kinds.setdefault(sid, set()).add(kind)
    return [{"id": s.id, "channel": s.channel, "created_at": s.created_at.isoformat(),
             "updated_at": s.updated_at.isoformat(), "messages": msg_counts.get(s.id, 0),
             "stages": sorted(kinds.get(s.id, set()))} for s in rows]


@router.get("/sessions/{session_id}/messages")
async def session_messages(session_id: str, admin: str = Depends(current_admin),
                           db: AsyncSession = Depends(get_db)):
    rows = (await db.execute(select(EventMessage).where(EventMessage.session_id == session_id)
                             .order_by(EventMessage.id))).scalars().all()
    return [{"role": m.role, "body": m.body, "created_at": m.created_at.isoformat()} for m in rows]


@router.get("/metrics")
async def metrics(admin: str = Depends(current_admin), db: AsyncSession = Depends(get_db)):
    async def sessions_with(kind: str) -> int:
        return (await db.execute(select(func.count(distinct(EventActivity.session_id)))
                                 .where(EventActivity.kind == kind))).scalar_one()

    total = (await db.execute(select(func.count(EventSession.id)))).scalar_one()
    pending = (await db.execute(select(func.count(EventPurchaseReport.id))
                                .where(EventPurchaseReport.status == "reported"))).scalar_one()
    confirmed = (await db.execute(select(EventPurchaseReport.confirmed_currency,
                                         func.sum(EventPurchaseReport.confirmed_amount_minor),
                                         func.count(EventPurchaseReport.id))
                                  .where(EventPurchaseReport.status == "confirmed")
                                  .group_by(EventPurchaseReport.confirmed_currency))).all()
    return {
        "sessions": total,
        "interest": await sessions_with("interest"),
        "selections": await sessions_with("selection"),
        "clicks": await sessions_with("click"),
        "human_requests": await sessions_with("human_request"),
        "payments_reported_pending": pending,
        "confirmed_purchases": sum(c for _, _, c in confirmed),
        # Only manually confirmed purchases count as revenue; empty list == "sin datos".
        "confirmed_revenue": [{"currency": cur, "total": fmt_minor(int(tot), cur)} for cur, tot, _ in confirmed],
        "attribution_note": ("Atribución manual: solo compras confirmadas por un administrador y "
                             "vinculadas a una conversación. Los clics no son ventas."),
    }


def _csv_cell(value) -> str:
    text = "" if value is None else str(value)
    return "'" + text if text[:1] in ("=", "+", "-", "@", "\t", "\r") else text


@router.get("/export/{kind}.csv")
async def export_csv(kind: Literal["activity", "selections", "purchases"],
                     admin: str = Depends(current_admin), db: AsyncSession = Depends(get_db)):
    rows = {"activity": lambda: _activity_rows(db, None, 5000),
            "selections": lambda: _selection_rows(db, 5000),
            "purchases": lambda: _purchase_rows(db, None, 5000)}[kind]
    data = await rows()
    buf = io.StringIO()
    if data:
        writer = csv.DictWriter(buf, fieldnames=list(data[0].keys()))
        writer.writeheader()
        for row in data:
            writer.writerow({k: _csv_cell(v) for k, v in row.items()})
    return Response(content="﻿" + buf.getvalue(), media_type="text/csv; charset=utf-8",
                    headers={"Content-Disposition": f'attachment; filename="sabi-eventos-{kind}.csv"'})
