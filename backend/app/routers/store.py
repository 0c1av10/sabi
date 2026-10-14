"""Per-restaurant storefront: onboarding from the owner's data/website, public store and web checkout.
Web orders land in the same approval inbox as WhatsApp orders and are confirmed only after approval."""
import re
import secrets
import unicodedata
from typing import Literal, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..auth import current_restaurant
from ..bcv import refresh_rates
from ..config import settings
from ..db import get_db
from ..importer import BASE_MENU, import_site, normalize_url
from ..models import Message, MenuItem, Order, OrderItem, Restaurant
from ..service import get_or_create_conversation, notify_owner_new_order

router = APIRouter(prefix="/api", tags=["store"])


class OnboardingIn(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    email: str = Field(min_length=5, max_length=200, pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
    phone: str = Field(min_length=7, max_length=30)
    website: str = Field(default="", max_length=300)


class CartItemIn(BaseModel):
    menu_item_id: int
    quantity: int = Field(ge=1, le=50)


class CheckoutIn(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    phone: str = Field(min_length=7, max_length=30)
    order_type: Literal["delivery", "retiro"] = "retiro"
    address: str = Field(default="", max_length=300)
    notes: str = Field(default="", max_length=500)
    payment_method: Literal["pago_movil", "zelle", "transferencia", "efectivo"] = "pago_movil"
    payment_reference: str = Field(default="", max_length=160)
    items: list[CartItemIn] = Field(min_length=1, max_length=40)


def _digits(phone: str) -> str:
    return re.sub(r"\D", "", phone)


def _slugify(text: str) -> str:
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")[:60] or "local"


async def _unique_slug(db: AsyncSession, name: str) -> str:
    base = _slugify(name)
    slug, n = base, 2
    while (await db.execute(select(Restaurant.id).where(Restaurant.slug == slug))).first():
        slug, n = f"{base}-{n}", n + 1
    return slug


def _color(value: str) -> str:
    return value if re.fullmatch(r"#[0-9a-fA-F]{6}", value or "") else ""


async def _apply_import(db: AsyncSession, restaurant: Restaurant, data: dict) -> int:
    """Upserts imported dishes by name; keeps the owner's existing dishes. Returns dishes added or updated."""
    existing = {m.name.lower(): m for m in (await db.execute(select(MenuItem).where(
        MenuItem.restaurant_id == restaurant.id))).scalars().all()}
    for it in data["items"]:
        mi = existing.get(it["name"].lower())
        if mi:
            mi.price = it["price"]
            mi.image_url = mi.image_url or it["image_url"]
        else:
            db.add(MenuItem(restaurant_id=restaurant.id, name=it["name"], price=it["price"],
                            category=it["category"], description=it["description"],
                            image_url=it["image_url"]))
    restaurant.logo_url = restaurant.logo_url or data["logo_url"]
    restaurant.brand_color = restaurant.brand_color or _color(data["brand_color"])
    restaurant.tagline = restaurant.tagline or data["tagline"]
    return len(data["items"])


@router.post("/onboarding")
async def onboarding(data: OnboardingIn, db: AsyncSession = Depends(get_db)):
    website = normalize_url(data.website)
    imported = await import_site(website) if website else None
    name = data.name.strip()
    r = Restaurant(
        name=name,
        slug=await _unique_slug(db, name),
        pin=f"{secrets.randbelow(10000):04d}",
        owner_phone=_digits(data.phone),
        email=data.email.strip().lower(),
        website=website,
        welcome_message=f"¡Hola! 👋 Soy Sabi de *{name}*. ¿Qué te provoca hoy?",
    )
    db.add(r)
    await db.flush()
    await refresh_rates(r, force=True)
    count = await _apply_import(db, r, imported) if imported and imported["items"] else 0
    if imported and not count:
        await _apply_import(db, r, {**imported, "items": []})
    if not count:
        for n, price, cat, desc in BASE_MENU:
            db.add(MenuItem(restaurant_id=r.id, name=n, price=price, category=cat, description=desc))
    await db.commit()
    return {
        "slug": r.slug, "pin": r.pin, "name": r.name,
        "imported": count, "site_read": bool(imported),
        "store_path": f"/tienda/{r.slug}",
    }


@router.get("/store/{slug}")
async def public_store(slug: str, db: AsyncSession = Depends(get_db)):
    r = (await db.execute(select(Restaurant).where(Restaurant.slug == slug))).scalar_one_or_none()
    if not r:
        raise HTTPException(404, "Tienda no encontrada")
    if await refresh_rates(r):
        await db.commit()
    items = (await db.execute(select(MenuItem).where(
        MenuItem.restaurant_id == r.id, MenuItem.available.is_(True)
    ).order_by(MenuItem.id))).scalars().all()
    return {
        "name": r.name, "slug": r.slug, "tagline": r.tagline, "logo_url": r.logo_url,
        "brand_color": r.brand_color or "#25D366", "opening_hours": r.opening_hours,
        "whatsapp": settings.shared_whatsapp_number or r.owner_phone,
        "rates": {"usd": r.exchange_rate, "eur": r.eur_rate},
        "menu": [{"id": i.id, "name": i.name, "price": i.price, "category": i.category,
                  "description": i.description, "image_url": i.image_url} for i in items],
    }


@router.post("/store/{slug}/orders")
async def store_checkout(slug: str, data: CheckoutIn, db: AsyncSession = Depends(get_db)):
    r = (await db.execute(select(Restaurant).where(Restaurant.slug == slug))).scalar_one_or_none()
    if not r:
        raise HTTPException(404, "Tienda no encontrada")
    if data.order_type == "delivery" and not data.address.strip():
        raise HTTPException(422, "Falta la dirección de entrega")
    menu = {i.id: i for i in (await db.execute(select(MenuItem).where(
        MenuItem.restaurant_id == r.id, MenuItem.available.is_(True)))).scalars().all()}
    lines = []
    for c in data.items:
        mi = menu.get(c.menu_item_id)
        if not mi:
            raise HTTPException(409, "Uno de los productos ya no está disponible")
        lines.append((mi, c.quantity))

    conv = await get_or_create_conversation(db, r, _digits(data.phone), data.name.strip())
    summary = ", ".join(f"{q}x {mi.name}" for mi, q in lines)
    db.add(Message(conversation_id=conv.id, direction="inbound",
                   body=f"🛒 Pedido desde la tienda web: {summary}"))
    order = Order(restaurant_id=r.id, conversation_id=conv.id, customer_id=conv.customer_id,
                  order_type=data.order_type, source="tienda",
                  address=data.address.strip() if data.order_type == "delivery" else "",
                  notes=data.notes.strip(), total=sum(mi.price * q for mi, q in lines),
                  payment_method=data.payment_method, payment_reference=data.payment_reference.strip(),
                  payment_status="submitted")
    db.add(order)
    await db.flush()
    for mi, q in lines:
        db.add(OrderItem(order_id=order.id, menu_item_id=mi.id, name=mi.name, quantity=q,
                         unit_price=mi.price))
    conv.status = "closed"
    await db.flush()
    await notify_owner_new_order(db, r, order)
    await db.commit()
    return {"order_id": order.id, "status": "pending", "total": order.total}


@router.post("/store/import")
async def reimport(restaurant: Restaurant = Depends(current_restaurant),
                   db: AsyncSession = Depends(get_db), website: Optional[str] = None):
    url = normalize_url(website or restaurant.website)
    if not url:
        raise HTTPException(400, "Agrega la página web del local")
    data = await import_site(url)
    if not data:
        raise HTTPException(502, "No pudimos abrir esa página web")
    restaurant.website = url
    count = await _apply_import(db, restaurant, data)
    await db.commit()
    return {"imported": count, "website": url}
