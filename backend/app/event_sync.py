"""Feeds the events catalog from TuEntradaWeb's public JSON (the same one its own site uses).

Read-only: a handful of GET requests to public listing/detail endpoints, no session, no
personal data, nothing about checkout. Each event gets the official link to its own page.
Prices are the platform's reference prices (they do NOT include its service fee).
"""
import re
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from urllib.parse import urlparse

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from .config import settings
from .event_models import CURRENCIES, Event, EventZone
from .event_service import to_minor, validate_purchase_url
from .models import utcnow

UA = "SabiEventsSync/1.0 (+https://www.holasabi.com)"
MAX_EVENTS = 60
STATUS_MAP = {"PUBLISHED": "publicado", "DRAFT": "borrador", "CANCELLED": "cancelado",
              "CANCELED": "cancelado", "FINISHED": "finalizado", "ENDED": "finalizado"}


def _base() -> str:
    return (settings.events_source_url or "").rstrip("/")


def _origin() -> str:
    p = urlparse(_base())
    return f"{p.scheme}://{p.netloc}"


def _dt(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        d = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if d.tzinfo:
        d = d.astimezone(timezone.utc).replace(tzinfo=None)
    return d


def collect_slugs(payload: dict) -> list[str]:
    """Slugs of every event in a listing page: loose events plus the events inside tours."""
    slugs: list[str] = []
    for item in payload.get("data") or []:
        if item.get("type") == "tour":
            for country in item.get("countries") or []:
                for city in country.get("cities") or []:
                    for ev in city.get("events") or []:
                        if ev.get("slug"):
                            slugs.append(ev["slug"])
        elif item.get("slug"):
            slugs.append(item["slug"])
    return slugs


def _html_to_text(value: str | None) -> str:
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", value or "")).strip()


def parse_event(data: dict) -> dict | None:
    """Detail payload -> fields for our Event + its zones. None when it can't be used."""
    slug = (data.get("slug") or "").strip()
    starts = _dt(data.get("starts_at"))
    venue = data.get("venue") or {}
    city = ((venue.get("city") or {}).get("name") or "").strip()
    if not slug or not starts or not city or not data.get("title"):
        return None
    currency = (data.get("currency") or "").upper()
    if currency not in CURRENCIES:
        return None
    sales_open = bool((data.get("venta") or {}).get("abierta", True)) and \
        bool(data.get("online_sales_enabled", True))
    zones = []
    for tt in data.get("ticket_types") or []:
        try:
            price = Decimal(str(tt.get("price")))
        except InvalidOperation:
            continue
        name = (tt.get("name") or "").strip()
        if not name or price <= 0 or price >= Decimal("10000000"):
            continue
        if not sales_open:
            availability = "por_confirmar"
        else:
            availability = "disponible" if (tt.get("available") or 0) > 0 else "agotado"
        zones.append({"name": name[:120], "price_minor": to_minor(price),
                      "currency": currency, "availability": availability})
    image = data.get("image") or ""
    return {
        "slug": slug[:120],
        "name": str(data["title"]).strip()[:200],
        "artist": (data.get("tour_name") or "")[:200],
        "city": city[:100],
        "venue": (venue.get("name") or "")[:200],
        "starts_at": starts,
        "description": (_html_to_text(data.get("short_description")) or
                        _html_to_text(data.get("description_html")))[:4000],
        "image_url": f"{_origin()}/{image.lstrip('/')}" if image and not image.startswith("http") else image,
        "status": STATUS_MAP.get(str(data.get("status", "")).upper(), "borrador"),
        "purchase_url": f"{_origin()}/eventos/{slug}/entradas",
        "zones": zones,
    }


async def _get_json(client: httpx.AsyncClient, url: str, params: dict | None = None) -> dict:
    r = await client.get(url, params=params)
    r.raise_for_status()
    body = r.json()
    return body if isinstance(body, dict) else {}


async def fetch_remote() -> list[dict]:
    """Download and parse the catalog. Raises httpx errors if the source is unreachable."""
    base = _base()
    if not base:
        raise RuntimeError("EVENTS_SOURCE_URL no está configurado")
    parsed: list[dict] = []
    async with httpx.AsyncClient(timeout=15, headers={"User-Agent": UA, "Accept": "application/json"}) as client:
        slugs: list[str] = []
        page = 1
        while page <= 5:
            payload = await _get_json(client, base, {"per_page": 50, "page": page})
            slugs += collect_slugs(payload)
            if page >= int(payload.get("last_page") or 1):
                break
            page += 1
        for slug in list(dict.fromkeys(slugs))[:MAX_EVENTS]:
            try:
                detail = (await _get_json(client, f"{base}/{slug}")).get("data") or {}
            except (httpx.HTTPError, ValueError):
                continue
            item = parse_event(detail)
            if item:
                parsed.append(item)
    return parsed


async def apply(db: AsyncSession, items: list[dict]) -> dict:
    """Upsert events and zones. Only events that came from the source are touched."""
    now = utcnow()
    created = updated = 0
    seen: set[str] = set()
    for it in items:
        try:
            url = validate_purchase_url(it["purchase_url"])
        except ValueError:
            url = ""
        ev = (await db.execute(select(Event).where(Event.slug == it["slug"])
                               .options(selectinload(Event.zones)))).scalar_one_or_none()
        if ev and ev.is_demo:
            continue
        seen.add(it["slug"])
        if not ev:
            ev = Event(slug=it["slug"], timezone="America/Caracas", active=True, is_demo=False)
            db.add(ev)
            created += 1
        else:
            updated += 1
        ev.name, ev.artist, ev.city, ev.venue = it["name"], it["artist"], it["city"], it["venue"]
        ev.starts_at, ev.description, ev.image_url = it["starts_at"], it["description"], it["image_url"]
        ev.status, ev.purchase_url, ev.updated_at = it["status"], url, now
        by_name = {z.name: z for z in ev.zones}
        names = set()
        for z in it["zones"]:
            names.add(z["name"])
            row = by_name.get(z["name"])
            if not row:
                ev.zones.append(EventZone(name=z["name"], price_minor=z["price_minor"],
                                          currency=z["currency"], availability=z["availability"],
                                          verified_at=now))
            else:
                row.price_minor, row.currency = z["price_minor"], z["currency"]
                row.availability, row.verified_at = z["availability"], now
        for name, row in by_name.items():
            if name not in names:  # no longer listed: don't claim it is available
                row.availability = "por_confirmar"
    deactivated = 0
    if seen:  # the real catalog replaces the demo events
        demos = (await db.execute(select(Event).where(Event.is_demo.is_(True), Event.active.is_(True)))).scalars().all()
        for d in demos:
            d.active = False
            deactivated += 1
    await db.commit()
    return {"created": created, "updated": updated, "demo_deactivated": deactivated, "total": len(seen)}


async def sync(db: AsyncSession) -> dict:
    items = await fetch_remote()
    if not items:
        return {"created": 0, "updated": 0, "demo_deactivated": 0, "total": 0,
                "note": "La fuente no devolvió eventos; no se cambió nada."}
    return await apply(db, items)
