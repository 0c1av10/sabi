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
from . import memory
from .models import Restaurant

WELCOME = (
    "¡Hola! 👋 Soy Sabi. Te echo una mano con lo que necesites: dónde comer o pedir delivery, "
    "conseguir entradas para un evento o reservar tu clase de boxeo. ¿Qué se te antoja hoy?"
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


GREETING = re.compile(
    r"^\W*(?:hola+|holi+|buenas|buen\s?dia|buenos\s?dias|buenas\s?(?:tardes|noches)|hey|hi|saludos|inicio|"
    r"menu|opciones|ayuda|que\s+(?:tienes|tienen|hay|ofreces|ofrecen)|en\s+que\s+me\s+ayudas)"
    r"(?:\s+(?:sabi|a\s+todos|amigo|amiga))?\W*$")


def is_greeting(body: str) -> bool:
    """A bare "hola" / "buenas" / "menú": it restarts the conversation with Sabi's options."""
    return bool(GREETING.match(_plain(body).strip()))


async def _places(db: AsyncSession, limit: int = 6) -> str:
    rows = (await db.execute(select(Restaurant).order_by(Restaurant.id).limit(limit))).scalars().all()
    if not rows:
        return ""
    lines = []
    for r in rows:
        tag = (r.tagline or "").strip()
        lines.append(f"• *{r.name}*" + (f" — {tag}" if tag else ""))
    return "🍽️ *Comida y delivery*\n" + "\n".join(lines) + "\n\n"


async def _hello(db: AsyncSession, name: str, returning: bool) -> str:
    who = f", {name}" if name else ""
    head = f"¡Hola de nuevo{who}! 👋" if returning else f"¡Hola{who}! 👋 Soy Sabi."
    return (f"{head} Esto es lo que tengo disponible:\n\n" + await _places(db) +
            "🎟️ *Entradas y eventos*: dime qué plan buscas, por ejemplo «¿qué hay por hacer en Lechería?».\n"
            "🥊 *Clases de boxeo* en Domicio Rondón Gym.\n\n"
            "¿Qué te provoca hoy? Escríbeme el nombre del sitio o lo que se te antoja.")


async def reply(db: AsyncSession, body: str, phone: str = "") -> tuple[str, bool]:
    """(text, is_plain_welcome). The welcome is rate-limited by the caller; recommendations are not."""
    contact = await memory.get(db, phone) if phone else None
    name = memory.first_name(contact.name if contact else None)
    said = memory.extract_name(body)
    if said and len(body.split()) <= 6:
        return (f"¡Mucho gusto, {memory.first_name(said)}! 😊 Ya me quedo con tu nombre. "
                "¿Qué se te antoja hoy: comida, entradas o una clase de boxeo?"), False
    sellers = await restaurants_by_product(db, body)
    if len(sellers) >= 2:
        names = "\n".join(f"• *{r.name}*" for r in sellers[:4])
        return ("¡Claro! 😋 Eso lo consigues en:\n" + names +
                f"\n\nDime dónde y te lo armo, por ejemplo «quiero pedir en {sellers[0].name}».", False)
    if wants_food(body):
        text = await recommendations(db)
        return (text.replace("¡Uy, qué rico!", f"¡Uy, qué rico, {name}!", 1) if name else text), False
    return await _hello(db, name, bool(contact and contact.last_topic)), True
