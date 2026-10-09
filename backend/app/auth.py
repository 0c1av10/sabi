from fastapi import Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from itsdangerous import URLSafeSerializer, BadSignature

from .config import settings
from .db import get_db
from .models import Restaurant

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
