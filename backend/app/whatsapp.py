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

    provider = whatsapp_provider()
    if settings.whatsapp_mock_mode or not provider:
        logger.info("[MOCK WA] -> %s: %s", to_phone, body)
        return {"mock": True, "to": to_phone}

    async with httpx.AsyncClient(timeout=20) as client:
        if provider == "zernio":
            return await _send_zernio(client, to_phone, body)
        if provider == "kapso":
            url = (f"https://api.kapso.ai/meta/whatsapp/{settings.kapso_api_version}/"
                   f"{settings.kapso_phone_number_id}/messages")
            headers = {"X-API-Key": settings.kapso_api_key}
        else:
            url = (f"https://graph.facebook.com/{settings.whatsapp_api_version}/"
                   f"{settings.whatsapp_phone_number_id}/messages")
            headers = {"Authorization": f"Bearer {settings.whatsapp_token}"}
        payload = {
            "messaging_product": "whatsapp",
            "to": to_phone,
            "type": "text",
            "text": {"body": body},
        }
        return await _post(client, url, payload, headers, to_phone)


async def send_whatsapp_reaction(to_phone: str, message_id: str, emoji: str) -> dict:
    """React to an inbound message with an emoji (Cloud API `reaction` message).
    Supported through Meta and Kapso. Zernio has no documented reaction endpoint, so there
    the agent's emoji-rich text reply carries the tone instead. Never raises."""
    if not (message_id and emoji):
        return {"skipped": "empty"}
    provider = whatsapp_provider()
    if settings.whatsapp_mock_mode or not provider:
        logger.info("[MOCK WA] react %s -> %s (%s)", emoji, to_phone, message_id)
        sent_log.append({"to": to_phone, "reaction": emoji, "message_id": message_id})
        return {"mock": True}
    if provider == "zernio":
        return {"skipped": "unsupported_provider"}
    if provider == "kapso":
        url = (f"https://api.kapso.ai/meta/whatsapp/{settings.kapso_api_version}/"
               f"{settings.kapso_phone_number_id}/messages")
        headers = {"X-API-Key": settings.kapso_api_key}
    else:
        url = (f"https://graph.facebook.com/{settings.whatsapp_api_version}/"
               f"{settings.whatsapp_phone_number_id}/messages")
        headers = {"Authorization": f"Bearer {settings.whatsapp_token}"}
    payload = {"messaging_product": "whatsapp", "to": to_phone, "type": "reaction",
               "reaction": {"message_id": message_id, "emoji": emoji}}
    async with httpx.AsyncClient(timeout=10) as client:
        return await _post(client, url, payload, headers, to_phone)


def whatsapp_provider() -> str:
    if settings.whatsapp_provider:
        return settings.whatsapp_provider
    if settings.zernio_api_key:
        return "zernio"
    if settings.kapso_api_key:
        return "kapso"
    return "meta" if settings.whatsapp_token else ""


def digits(phone: str) -> str:
    return "".join(c for c in phone if c.isdigit())


ZERNIO_API = "https://zernio.com/api/v1"
# phone (digits) -> Zernio conversation id, filled by the inbound webhook.
zernio_conversations: dict[str, str] = {}


async def _send_zernio(client: httpx.AsyncClient, to_phone: str, body: str) -> dict:
    headers = {"Authorization": f"Bearer {settings.zernio_api_key}"}
    phone = digits(to_phone)
    conv_id = zernio_conversations.get(phone)
    if not conv_id:
        try:
            resp = await client.get(f"{ZERNIO_API}/inbox/conversations", headers=headers, params={
                "accountId": settings.zernio_account_id, "platform": "whatsapp", "limit": 100})
            data = resp.json() if resp.status_code < 400 else {}
        except (httpx.HTTPError, ValueError) as exc:
            logger.error("Zernio conversation lookup failed: %s", exc)
            data = {}
        items = data.get("data") or data.get("conversations") or [] if isinstance(data, dict) else []
        conv_id = next((c.get("id") for c in items
                        if digits(str(c.get("participantId", ""))) == phone), None)
        if not conv_id:
            logger.error("Zernio: no conversation for %s", to_phone)
            return {"error": "no_conversation"}
        zernio_conversations[phone] = conv_id
    return await _post(client, f"{ZERNIO_API}/inbox/conversations/{conv_id}/messages",
                       {"accountId": settings.zernio_account_id, "message": body}, headers, to_phone)


async def _post(client: httpx.AsyncClient, url: str, payload: dict, headers: dict,
                to_phone: str) -> dict:
    try:
        resp = await client.post(url, json=payload, headers=headers)
    except httpx.HTTPError as exc:
        logger.error("WhatsApp send error to %s: %s", to_phone, exc)
        return {"error": str(exc)}
    if resp.status_code >= 400:
        logger.error("WhatsApp send failed %s: %s", resp.status_code, resp.text[:500])
        return {"error": resp.status_code}
    return resp.json()
