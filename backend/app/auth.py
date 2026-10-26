from fastapi import Depends, HTTPException, Request
import re
import unicodedata

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from itsdangerous import URLSafeSerializer, BadSignature

from .config import settings
from .db import get_db
from .models import Conversation, Customer, MenuItem, Restaurant

_serializer = URLSafeSerializer(settings.session_secret, salt="sabi-auth")
COOKIE_NAME = "sabi_session"


def make_token(restaurant_id: int) -> str:
    return _serializer.dumps({"rid": restaurant_id})


def parse_token(token: str) -> int | None:
    try:
        return _serializer.loads(token).get("rid")
    except BadSignature:
        return None


async def current_restaurant(request: Request, db: AsyncSession = Depends(get_db)) -> Restaurant:
    token = request.cookies.get(COOKIE_NAME) or request.headers.get("X-Sabi-Token", "")
    rid = parse_token(token) if token else None
    if rid is None:
        raise HTTPException(401, "No autenticado")
    restaurant = await db.get(Restaurant, rid)
    if not restaurant:
        raise HTTPException(401, "Restaurante no encontrado")
    return restaurant


async def restaurant_for_webhook(db: AsyncSession) -> Restaurant:
    """MVP: single WhatsApp number = single restaurant (first one). Extend by
    mapping phone_number_id -> restaurant when multi-tenant."""
    return (await db.execute(select(Restaurant))).scalars().first()


_GENERIC = {"restaurante", "restaurant", "resto", "bar", "cafe", "cafeteria", "el", "la", "los",
            "las", "de", "del", "y", "&"}


def _norm(text: str) -> list[str]:
    plain = unicodedata.normalize("NFD", text.lower())
    plain = "".join(c for c in plain if unicodedata.category(c) != "Mn")
    return re.findall(r"[a-z0-9]+", plain)


async def restaurant_by_mention(db: AsyncSession, body: str) -> Restaurant | None:
    """A first message such as "hola, quiero pedir en Nacional" names the business.
    Matches when every distinctive word of the name (or the slug) appears in the message;
    the longest match wins and a tie is treated as ambiguous (no routing)."""
    words = set(_norm(body))
    if not words:
        return None
    best: list[tuple[int, Restaurant]] = []
    for r in (await db.execute(select(Restaurant))).scalars().all():
        for candidate in (_norm(r.name), _norm(r.slug)):
            core = [w for w in candidate if w not in _GENERIC]
            if core and all(w in words for w in core):
                best.append((len(core), r))
                break
    if not best:
        return None
    top = max(n for n, _ in best)
    winners = [r for n, r in best if n == top]
    return winners[0] if len(winners) == 1 else None


_PRODUCT_STOP = {"quiero", "unos", "unas", "pedir", "para", "compartir", "piezas", "pieza", "pzas", "individual",
                 "combo", "combos", "natural", "casero", "entero", "medio", "platos", "entradas", "postres",
                 "bebidas", "general", "algo", "hola", "buenas", "favor", "necesito", "gustaria", "tienen",
                 "tiene", "hay", "unos", "dame", "mandame", "ordenar", "comprar", "ocupo", "busco", "mucho"}


def _stem(word: str) -> str:
    for suffix in ("es", "s"):
        if word.endswith(suffix) and len(word) - len(suffix) >= 4:
            return word[: -len(suffix)]
    return word


def _same(a: str, b: str) -> bool:
    return a == b or (min(len(a), len(b)) >= 6 and (a.startswith(b) or b.startswith(a)))


async def restaurants_by_product(db: AsyncSession, body: str) -> list[Restaurant]:
    """Businesses whose available menu has a product the message asks for ("quiero unos pastelitos").
    Only distinctive words count (4+ letters, not filler)."""
    wanted = {_stem(w) for w in _norm(body) if len(w) >= 4 and w not in _PRODUCT_STOP}
    if not wanted:
        return []
    found: dict[int, Restaurant] = {}
    rows = (await db.execute(select(MenuItem, Restaurant).join(
        Restaurant, MenuItem.restaurant_id == Restaurant.id).where(MenuItem.available.is_(True)))).all()
    for item, rest in rows:
        words = {_stem(w) for w in _norm(f"{item.name} {item.category}") if len(w) >= 4 and w not in _PRODUCT_STOP}
        if any(_same(w, m) for w in wanted for m in words):
            found[rest.id] = rest
    return list(found.values())


async def restaurant_for_message(db: AsyncSession, phone: str, body: str) -> tuple[Restaurant | None, str]:
    """Resolve a shared WhatsApp message to a tenant.

    Click-to-WhatsApp links include ``[sabi:<slug>]``. Once a conversation is
    open, subsequent messages stay with that restaurant even without the tag.
    """
    match = re.search(r"\[sabi:([a-z0-9-]+)\]", body.lower())
    if match:
        restaurant = (await db.execute(
            select(Restaurant).where(Restaurant.slug == match.group(1))
        )).scalar_one_or_none()
        if restaurant:
            return restaurant, re.sub(r"\s*\[sabi:[a-z0-9-]+\]\s*", " ", body, flags=re.I).strip()

    mentioned = await restaurant_by_mention(db, body)
    if mentioned:
        return mentioned, body

    restaurant = (await db.execute(
        select(Restaurant)
        .join(Customer, Customer.restaurant_id == Restaurant.id)
        .join(Conversation, Conversation.customer_id == Customer.id)
        .where(Customer.phone == phone, Conversation.status == "open")
        .order_by(Conversation.updated_at.desc())
    )).scalars().first()
    if restaurant:
        return restaurant, body
    # No business named and no open conversation: a product only one business sells decides it.
    by_product = await restaurants_by_product(db, body)
    if len(by_product) == 1:
        return by_product[0], body
    return None, body
