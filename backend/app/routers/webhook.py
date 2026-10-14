from fastapi import APIRouter, Depends, Query, Request, Response
from sqlalchemy.ext.asyncio import AsyncSession

from ..auth import restaurant_for_webhook
from ..config import settings
from ..db import get_db
from ..service import handle_inbound_message, recent_inbound_count

router = APIRouter(tags=["whatsapp"])


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
    restaurant = await restaurant_for_webhook(db)
    if not restaurant:
        return {"status": "no_restaurant"}

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
                    await handle_inbound_message(db, restaurant, phone, body, name)
    return {"status": "ok"}


# Local simulator: same pipeline without Meta's payload envelope.
@router.post("/webhook/simulate")
async def simulate_message(body_in: dict, db: AsyncSession = Depends(get_db)):
    restaurant = await restaurant_for_webhook(db)
    if not restaurant:
        return {"reply": ""}
    if await recent_inbound_count(db) >= settings.simulate_limit_hour:
        return {"reply": "La demo recibió muchos mensajes en la última hora. Prueba de nuevo más tarde."}
    phone = body_in.get("phone", "59912345678")
    text = body_in.get("text", "")
    name = body_in.get("name", "Cliente Test")
    reply = await handle_inbound_message(db, restaurant, phone, text, name)
    return {"reply": reply}
