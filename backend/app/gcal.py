"""Google Calendar for gym classes, through a service account (no user login needed).

The gym shares its calendar with the service account's email ("Make changes to events") and
pastes the calendar id in the panel. Sabi then checks for clashes and creates one event per
confirmed class. Nothing is read from or written to any other calendar.
"""
import asyncio
import base64
import json
from datetime import datetime, timedelta, timezone

import httpx

from .config import settings

API = "https://www.googleapis.com/calendar/v3/calendars"
SCOPE = "https://www.googleapis.com/auth/calendar.events"
TZ_NAME = "America/Caracas"
_CARACAS = timezone(timedelta(hours=-4))


class CalendarError(Exception):
    pass


def _info() -> dict | None:
    raw = (settings.google_service_account_json or "").strip()
    if not raw:
        return None
    try:
        if not raw.startswith("{"):
            raw = base64.b64decode(raw).decode()
        data = json.loads(raw)
    except Exception:  # noqa: BLE001
        return None
    return data if isinstance(data, dict) and data.get("client_email") and data.get("private_key") else None


def enabled() -> bool:
    return _info() is not None


def service_email() -> str:
    info = _info()
    return info["client_email"] if info else ""


def _token_sync() -> str:
    from google.auth.transport.requests import Request
    from google.oauth2 import service_account
    creds = service_account.Credentials.from_service_account_info(_info(), scopes=[SCOPE])
    creds.refresh(Request())
    return creds.token


async def _headers() -> dict:
    try:
        token = await asyncio.to_thread(_token_sync)
    except Exception as exc:  # noqa: BLE001
        raise CalendarError("No se pudo autenticar con Google Calendar") from exc
    return {"Authorization": f"Bearer {token}"}


def _local_iso(dt_utc: datetime) -> str:
    return dt_utc.replace(tzinfo=timezone.utc).astimezone(_CARACAS).isoformat()


async def clashes(calendar_id: str, start_utc: datetime, end_utc: datetime) -> list[str]:
    """Titles of events overlapping the slot (empty list = free)."""
    headers = await _headers()
    params = {"timeMin": start_utc.replace(tzinfo=timezone.utc).isoformat(),
              "timeMax": end_utc.replace(tzinfo=timezone.utc).isoformat(),
              "singleEvents": "true", "maxResults": "10"}
    async with httpx.AsyncClient(timeout=15) as client:
        r = await client.get(f"{API}/{calendar_id}/events", params=params, headers=headers)
    if r.status_code in (403, 404):
        raise CalendarError("Sabi no tiene acceso a ese calendario: compártelo con "
                            f"{service_email()} con permiso para hacer cambios en eventos")
    if r.status_code >= 400:
        raise CalendarError(f"Google Calendar respondió {r.status_code}")
    return [e.get("summary", "(sin título)") for e in r.json().get("items", []) if e.get("status") != "cancelled"]


async def create_event(calendar_id: str, summary: str, description: str,
                       start_utc: datetime, end_utc: datetime) -> tuple[str, str]:
    headers = await _headers()
    body = {"summary": summary, "description": description,
            "start": {"dateTime": _local_iso(start_utc), "timeZone": TZ_NAME},
            "end": {"dateTime": _local_iso(end_utc), "timeZone": TZ_NAME}}
    async with httpx.AsyncClient(timeout=15) as client:
        r = await client.post(f"{API}/{calendar_id}/events", json=body, headers=headers)
    if r.status_code in (403, 404):
        raise CalendarError("Sabi no tiene acceso a ese calendario: compártelo con "
                            f"{service_email()} con permiso para hacer cambios en eventos")
    if r.status_code >= 400:
        raise CalendarError(f"Google Calendar respondió {r.status_code}")
    data = r.json()
    return data.get("id", ""), data.get("htmlLink", "")
