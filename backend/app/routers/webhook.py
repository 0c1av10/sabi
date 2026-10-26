import hashlib
import hmac
import json
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, Query, Request, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..auth import restaurant_for_message
from ..config import settings
from ..db import get_db
from ..models import Restaurant
from ..reactions import reaction_for
from ..whatsapp import digits, send_whatsapp_message, send_whatsapp_reaction, zernio_conversations
from ..service import handle_inbound_message, recent_inbound_count
from ..event_whatsapp import handle_event_whatsapp, wants_events
from .. import concierge, gym_whatsapp

router = APIRouter(tags=["whatsapp"])


WELCOME_MESSAGE = concierge.WELCOME
_WELCOME_COOLDOWN = timedelta(hours=1)
_welcomed: dict[str, datetime] = {}  # per warm instance: avoids repeating the welcome on every message


async def _react(phone: str, message_id: str | None, body: str) -> None:
    """Best-effort emoji reaction chosen by message type; must never break the reply."""
    emoji = reaction_for(body)
    if emoji and message_id:
        try:
            await send_whatsapp_reaction(phone, message_id, emoji)
        except Exception:  # noqa: BLE001
            pass


async def _resolve(db: AsyncSession, phone: str, body: str):
    """(restaurant, body, reply). `reply` is Sabi's concierge text when no business is named
    (None when a plain welcome was already sent recently)."""
    restaurant, routed_body = await restaurant_for_message(db, phone, body)
    if restaurant:
        return restaurant, routed_body, None
    text, is_welcome = await concierge.reply(db, body)
    if is_welcome:
        now = datetime.now(timezone.utc)
        last = _welcomed.get(phone)
        if last and now - last <= _WELCOME_COOLDOWN:
            return None, body, None
        _welcomed[phone] = now
    return None, body, text


async def _route_or_explain(db: AsyncSession, phone: str, body: str):
    restaurant, routed_body, reply = await _resolve(db, phone, body)
    if reply:
        await send_whatsapp_message(phone, reply)
    return restaurant, routed_body


async def _events_route(db: AsyncSession, phone: str, body: str, external_id: str | None = None):
    """Events assistant channel. Returns the reply text, or None if the message is not for it."""
    if await gym_whatsapp.wants_gym(db, phone, body):
        return await gym_whatsapp.handle_gym_whatsapp(db, phone, body)
    if not await wants_events(db, phone, body):
        return None
    return await handle_event_whatsapp(db, phone, body, external_id)


@router.get("/webhook/whatsapp")
async def verify_webhook(
    hub_mode: str = Query("", alias="hub.mode"),
    hub_verify_token: str = Query("", alias="hub.verify_token"),
    hub_challenge: str = Query("", alias="hub.challenge"),
):
    if hub_mode == "subscribe" and hub_verify_token == settings.whatsapp_verify_token:
        return Response(content=hub_challenge, media_type="text/plain")
    return Response(status_code=403)


@router.post("/webhook/whatsapp")
async def receive_webhook(request: Request, db: AsyncSession = Depends(get_db)):
    payload = await request.json()
    for entry in payload.get("entry", []):
        for change in entry.get("changes", []):
            value = change.get("value", {})
            for msg in value.get("messages", []):
                if msg.get("type") != "text":
                    continue
                phone = msg.get("from", "")
                body = msg.get("text", {}).get("body", "")
                name = ""
                for c in value.get("contacts", []):
                    if c.get("wa_id") == phone:
                        name = c.get("profile", {}).get("name", "")
                if phone and body:
                    await _react(phone, msg.get("id"), body)
                    if await _events_route(db, phone, body, msg.get("id")) is not None:
                        continue
                    restaurant, body = await _route_or_explain(db, phone, body)
                    if not restaurant:
                        continue
                    await handle_inbound_message(db, restaurant, phone, body, name,
                                                 external_id=msg.get("id"))
    return {"status": "ok"}


@router.post("/webhook/kapso")
async def receive_kapso(request: Request, db: AsyncSession = Depends(get_db)):
    raw = await request.body()
    secret = settings.kapso_webhook_secret
    expected = hmac.new(secret.encode(), raw, hashlib.sha256).hexdigest() if secret else ""
    if not secret or not hmac.compare_digest(expected, request.headers.get("X-Webhook-Signature", "")):
        return Response(status_code=401)
    if request.headers.get("X-Webhook-Event") != "whatsapp.message.received":
        return {"status": "ignored"}
    data = json.loads(raw)
    for item in data.get("data", []) if data.get("batch") else [data]:
        msg = item.get("message") or {}
        conv = item.get("conversation") or {}
        if msg.get("type") != "text" or (msg.get("kapso") or {}).get("direction", "inbound") != "inbound":
            continue
        phone = msg.get("from") or conv.get("phone_number") or ""
        body = (msg.get("text") or {}).get("body", "")
        if phone and body:
            await _react(phone, msg.get("id"), body)
            if await _events_route(db, phone, body, msg.get("id")) is not None:
                continue
            restaurant, body = await _route_or_explain(db, phone, body)
            if not restaurant:
                continue
            await handle_inbound_message(db, restaurant, phone, body, conv.get("contact_name") or "",
                                         external_id=msg.get("id"))
    return {"status": "ok"}


# Local simulator: same pipeline without Meta's payload envelope.
@router.post("/webhook/simulate")
async def simulate_message(body_in: dict, db: AsyncSession = Depends(get_db)):
    if await recent_inbound_count(db) >= settings.simulate_limit_hour:
        return {"reply": "La demo recibió muchos mensajes en la última hora. Prueba de nuevo más tarde."}
    phone = body_in.get("phone", "59912345678")
    text = body_in.get("text", "")
    name = body_in.get("name", "Cliente Test")
    events_reply = await _events_route(db, phone, text)
    if events_reply is not None:
        return {"reply": events_reply}
    restaurant, text, concierge_reply = await _resolve(db, phone, text)
    if not restaurant:
        return {"reply": concierge_reply or WELCOME_MESSAGE}
    reply = await handle_inbound_message(db, restaurant, phone, text, name)
    return {"reply": reply}


@router.post("/webhook/zernio")
async def receive_zernio(request: Request, db: AsyncSession = Depends(get_db)):
    raw = await request.body()
    secret = settings.zernio_webhook_secret
    expected = hmac.new(secret.encode(), raw, hashlib.sha256).hexdigest() if secret else ""
    if not secret or not hmac.compare_digest(expected, request.headers.get("X-Zernio-Signature", "")):
        return Response(status_code=401)
    data = json.loads(raw)
    if data.get("event") != "message.received":
        return {"status": "ignored"}
    msg = data.get("message") or {}
    sender = msg.get("sender") or {}
    if (msg.get("direction") != "incoming" or msg.get("platform") != "whatsapp"
            or (data.get("metadata") or {}).get("standby")):
        return {"status": "ignored"}
    phone = digits(sender.get("phoneNumber") or sender.get("id") or "")
    body = msg.get("text") or ""
    if msg.get("conversationId"):
        zernio_conversations[phone] = msg["conversationId"]
    external_id = msg.get("platformMessageId") or msg.get("id")
    if phone and body and await _events_route(db, phone, body, external_id) is not None:
        return {"status": "ok"}
    restaurant, body = await _route_or_explain(db, phone, body)
    if not (restaurant and phone and body):
        return {"status": "ignored"}
    await handle_inbound_message(db, restaurant, phone, body, sender.get("name") or "",
                                 external_id=msg.get("platformMessageId") or msg.get("id"))
    return {"status": "ok"}
