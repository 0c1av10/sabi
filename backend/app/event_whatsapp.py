"""WhatsApp channel adapter for the events assistant.

The conversation engine is channel independent (`run_event_agent`); this module only
routes inbound WhatsApp messages to it and renders the reply as plain text. Sending goes
through whatsapp.py, so it works with whichever provider is configured (Zernio, Kapso, Meta).
Authenticity of the webhook itself is checked by the provider routes in routers/webhook.py.
"""
import json
import re
import uuid
from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .config import settings
from .event_agent import run_event_agent
from .event_models import EventMessage, EventSession
from .event_service import get_or_create_session, recent_user_messages
from .models import utcnow
from .whatsapp import digits, send_whatsapp_message

EVENTS_TAG = re.compile(r"\[sabi:eventos\]", re.I)
OTHER_TAG = re.compile(r"\[sabi:(?!eventos\])[a-z0-9-]+\]", re.I)
_NAMESPACE = uuid.UUID("6f0f6c1e-5d0b-4a43-9a5f-2f4d8c1b7a10")
SESSION_TTL = timedelta(hours=12)
RATE_LIMIT_REPLY = "Recibimos muchos mensajes tuyos en poco tiempo. Espera un rato y vuelve a escribirnos, por favor."


def session_id_for(phone: str) -> str:
    """Stable id per WhatsApp number without storing the number itself."""
    return str(uuid.uuid5(_NAMESPACE, "wa:" + digits(phone)))


async def wants_events(db: AsyncSession, phone: str, body: str) -> bool:
    """True for the `[sabi:eventos]` entry tag, or while an events chat is active (12 h).
    A restaurant tag always wins so testers can switch back."""
    if OTHER_TAG.search(body):
        return False
    if EVENTS_TAG.search(body):
        return True
    session = await db.get(EventSession, session_id_for(phone))
    return bool(session and session.updated_at >= utcnow() - SESSION_TTL)


def render_text(reply: str, ui: list[dict]) -> str:
    parts = [reply]
    for block in ui:
        if block["type"] == "link" and block.get("habilitado") and block.get("ruta"):
            parts.append(f"{block.get('texto_boton', 'Ver disponibilidad y comprar en TuEntradaWeb')}:\n"
                         f"{settings.frontend_base_url.rstrip('/')}{block['ruta']}")
            if block.get("aviso"):
                parts.append(block["aviso"])
    return "\n\n".join(parts)


async def handle_event_whatsapp(db: AsyncSession, phone: str, body: str,
                                external_id: str | None = None) -> str:
    """Process one inbound WhatsApp message. Returns the text sent ('' if ignored)."""
    if external_id and (await db.execute(select(EventMessage.id).where(
            EventMessage.external_id == external_id))).first():
        return ""  # duplicate delivery
    message = EVENTS_TAG.sub(" ", body).strip()[:settings.events_max_message_chars] or "hola"

    session = await get_or_create_session(db, session_id_for(phone), channel="whatsapp", trusted_id=True)
    if (await recent_user_messages(db, session.id) >= settings.events_chat_limit_hour
            or await recent_user_messages(db) >= settings.events_global_limit_hour):
        await send_whatsapp_message(phone, RATE_LIMIT_REPLY)
        return RATE_LIMIT_REPLY
    db.add(EventMessage(session_id=session.id, role="user", body=message, external_id=external_id))
    await db.commit()  # visible to concurrent retries (dedupe) and to the agent's history

    result = await run_event_agent(db, session, message)
    text = render_text(result.reply, result.ui)
    session.state_json = json.dumps(result.state, ensure_ascii=False)
    db.add(EventMessage(session_id=session.id, role="assistant", body=text))
    await db.commit()
    await send_whatsapp_message(phone, text)
    return text
