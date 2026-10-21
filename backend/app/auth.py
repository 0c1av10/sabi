from fastapi import Depends, HTTPException, Request
import re
import unicodedata

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from itsdangerous import URLSafeSerializer, BadSignature

from .config import settings
from .db import get_db
from .models import Conversation, Customer, Restaurant

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
    return restaurant, body
