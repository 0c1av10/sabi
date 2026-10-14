from fastapi import Depends, HTTPException, Request
import re

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

    restaurant = (await db.execute(
        select(Restaurant)
        .join(Customer, Customer.restaurant_id == Restaurant.id)
        .join(Conversation, Conversation.customer_id == Customer.id)
        .where(Customer.phone == phone, Conversation.status == "open")
        .order_by(Conversation.updated_at.desc())
    )).scalars().first()
    return restaurant, body
