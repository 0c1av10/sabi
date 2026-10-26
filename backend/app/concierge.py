"""Sabi's reply when a message names no business: a friendly concierge that recommends.

Sabi is one assistant for many businesses, so it never introduces itself as the assistant of a
particular restaurant or producer. It chats naturally and, when asked about food or delivery,
recommends the places it knows; tickets are handled by the events assistant.
"""
import re
import unicodedata

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .auth import restaurants_by_product
from .models import Restaurant

WELCOME = (
    "¡Hola! 👋 Soy Sabi. Te echo una mano con lo que necesites: dónde comer o pedir delivery, "
    "o conseguir entradas para un evento. ¿Qué se te antoja hoy?"
)

FOOD_INTENT = re.compile(
    r"\b(comer|comida|comidita|cenar|cena|almorzar|almuerzo|desayun\w*|hambre|hambriento|antoj\w*|"
    r"restaurante\w*|restaurant|delivery|domicilio|pedir|pedido|pizza|hamburguesa\w*|parrilla|"
    r"sitio\w* para|lugar\w* para|donde (?:comer|cenar|almorzar)|recomiend\w*|provoca)\b")


def _plain(text: str) -> str:
    nfkd = unicodedata.normalize("NFKD", text or "")
    return "".join(c for c in nfkd if not unicodedata.combining(c)).lower()


def wants_food(body: str) -> bool:
    return bool(FOOD_INTENT.search(_plain(body)))


async def recommendations(db: AsyncSession, limit: int = 4) -> str:
    rows = (await db.execute(select(Restaurant).order_by(Restaurant.id).limit(limit))).scalars().all()
    if not rows:
        return ("Todavía no tengo locales para recomendarte por aquí, pero cuéntame qué se te antoja "
                "y lo tengo en cuenta. 😊 Si buscas entradas para un evento, dímelo y te ayudo.")
    lines = []
    for r in rows:
        tag = (r.tagline or "").strip()
        lines.append(f"• *{r.name}*" + (f" — {tag}" if tag else ""))
    first = rows[0].name
    return ("¡Uy, qué rico! 😋 Por ahora te recomiendo:\n" + "\n".join(lines) +
            f"\n\nSi te provoca alguno, escríbeme «quiero pedir en {first}» y te armo el pedido "
            "con delivery. ¿Qué se te antoja?")


async def reply(db: AsyncSession, body: str) -> tuple[str, bool]:
    """(text, is_plain_welcome). The welcome is rate-limited by the caller; recommendations are not."""
    sellers = await restaurants_by_product(db, body)
    if len(sellers) >= 2:
        names = "\n".join(f"• *{r.name}*" for r in sellers[:4])
        return ("¡Claro! 😋 Eso lo consigues en:\n" + names +
                f"\n\nDime dónde y te lo armo, por ejemplo «quiero pedir en {sellers[0].name}».", False)
    if wants_food(body):
        return await recommendations(db), False
    return WELCOME, True
