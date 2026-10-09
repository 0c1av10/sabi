import logging

import httpx

from .config import settings

logger = logging.getLogger("sabi.whatsapp")

# In-memory log of "sent" messages for mock mode / local testing.
sent_log: list[dict] = []


async def send_whatsapp_message(to_phone: str, body: str) -> dict:
    """Send a text message via WhatsApp Cloud API, or log it in mock mode."""
    entry = {"to": to_phone, "body": body}
    sent_log.append(entry)

    if settings.whatsapp_mock_mode or not settings.whatsapp_token:
        logger.info("[MOCK WA] -> %s: %s", to_phone, body)
        return {"mock": True, "to": to_phone}

    url = (
        f"https://graph.facebook.com/{settings.whatsapp_api_version}/"
        f"{settings.whatsapp_phone_number_id}/messages"
    )
    payload = {
        "messaging_product": "whatsapp",
        "to": to_phone,
        "type": "text",
        "text": {"body": body},
    }
    async with httpx.AsyncClient(timeout=20) as client:
        resp = await client.post(
            url,
            json=payload,
            headers={"Authorization": f"Bearer {settings.whatsapp_token}"},
        )
        if resp.status_code >= 400:
            logger.error("WhatsApp send failed %s: %s", resp.status_code, resp.text)
        resp.raise_for_status()
        return resp.json()
