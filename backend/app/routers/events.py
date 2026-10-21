"""Public endpoints of the events assistant: catalog, chat, selection and tracked redirect."""
import json
import re
import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from ..config import settings
from ..db import get_db
from ..event_agent import run_event_agent, uses_demo_engine
from ..event_models import Event, EventActivity, EventMessage, EventSelection, EventSession
from ..event_service import (NO_LINK_MESSAGE, VERIFY_NOTE, EventTools, event_public,
                             get_or_create_session, load_state, purchase_enabled,
                             platform_url, recent_user_messages, validate_purchase_url)
from ..models import utcnow

router = APIRouter(prefix="/api/events", tags=["events"])

_LINK_PREVIEW_BOTS = re.compile(r"(bot|crawler|spider|preview|facebookexternalhit|whatsapp|slackbot)", re.I)


class ChatIn(BaseModel):
    session_id: str | None = Field(None, max_length=36)
    message: str = Field(..., min_length=1, max_length=4000)


class SelectIn(BaseModel):
    session_id: str | None = Field(None, max_length=36)
    # Kept loose on purpose: the tool applies the strict validation (no floats, no strings).
    event_id: Any
    zone_id: Any
    quantity: Any


class HumanIn(BaseModel):
    session_id: str | None = Field(None, max_length=36)
    motivo: str = Field("Solicitud desde el chat web", min_length=1, max_length=300)


async def _upcoming_published(db: AsyncSession) -> list[Event]:
    return (await db.execute(
        select(Event).where(Event.status == "publicado", Event.active.is_(True),
                            Event.starts_at >= utcnow())
        .options(selectinload(Event.zones)).order_by(Event.starts_at))).scalars().all()


@router.get("/status")
async def status(db: AsyncSession = Depends(get_db)):
    events = await _upcoming_published(db)
    return {
        "engine": "demo" if uses_demo_engine() else "claude",
        "demo_data": any(e.is_demo for e in events),
        "events": len(events),
        "purchase_links_enabled": sum(1 for e in events if purchase_enabled(e)),
        "max_quantity": settings.events_max_quantity,
        "stale_hours": settings.events_stale_hours,
        "notice": VERIFY_NOTE,
    }


@router.get("")
async def catalog(db: AsyncSession = Depends(get_db)):
    return {"eventos": [event_public(e) for e in await _upcoming_published(db)], "aviso": VERIFY_NOTE}


@router.get("/go/cartelera")
async def go_to_platform(request: Request, c: str | None = None, db: AsyncSession = Depends(get_db)):
    """Tracked redirect to the official TuEntradaWeb listing (from settings, never from the request)."""
    destination = platform_url()
    if not destination:
        raise HTTPException(404, NO_LINK_MESSAGE)
    session_id = None
    if c:
        try:
            uuid.UUID(c)
            session_id = c if await db.get(EventSession, c) else None
        except ValueError:
            session_id = None
    if not _LINK_PREVIEW_BOTS.search(request.headers.get("user-agent", "")):
        db.add(EventActivity(session_id=session_id, event_id=None, kind="click",
                             detail="cartelera oficial abierta (no implica compra)"))
        await db.commit()
    return RedirectResponse(destination, status_code=302,
                            headers={"Cache-Control": "no-store", "Referrer-Policy": "no-referrer"})


@router.get("/go/{event_id}")
async def go_to_official_link(event_id: int, request: Request, c: str | None = None,
                              s: str | None = None, db: AsyncSession = Depends(get_db)):
    """Tracked redirect. The destination is ALWAYS read from the catalog record, never from
    the request, so this cannot be used as an open redirect. A click is not a sale."""
    event = (await db.execute(select(Event).where(Event.id == event_id))).scalar_one_or_none()
    if event is None or not event.active or not purchase_enabled(event):
        raise HTTPException(404, NO_LINK_MESSAGE)
    try:
        destination = validate_purchase_url(event.purchase_url)
    except ValueError:
        raise HTTPException(404, NO_LINK_MESSAGE)

    session_id = None
    if c:
        try:
            uuid.UUID(c)
            session_id = c if await db.get(EventSession, c) else None
        except ValueError:
            session_id = None
    selection_id = None
    if s and session_id:
        sel = await db.get(EventSelection, s)
        if sel and sel.session_id == session_id and sel.event_id == event.id:
            selection_id = sel.id
    ua = request.headers.get("user-agent", "")
    if not _LINK_PREVIEW_BOTS.search(ua):
        db.add(EventActivity(session_id=session_id, event_id=event.id, selection_id=selection_id,
                             kind="click", detail="enlace oficial abierto (no implica compra)"))
        await db.commit()
    return RedirectResponse(destination, status_code=302,
                            headers={"Cache-Control": "no-store", "Referrer-Policy": "no-referrer"})


@router.get("/{event_id}")
async def event_detail(event_id: int, db: AsyncSession = Depends(get_db)):
    event = (await db.execute(select(Event).where(Event.id == event_id)
                              .options(selectinload(Event.zones)))).scalar_one_or_none()
    if event is None or not event.active or event.status == "borrador":
        raise HTTPException(404, "Evento no encontrado")
    return {"evento": event_public(event), "aviso": VERIFY_NOTE}


@router.post("/chat")
async def chat(data: ChatIn, db: AsyncSession = Depends(get_db)):
    message = data.message.strip()[:settings.events_max_message_chars]
    if not message:
        raise HTTPException(422, "Escribe un mensaje")
    session = await get_or_create_session(db, data.session_id)
    if (await recent_user_messages(db, session.id) >= settings.events_chat_limit_hour
            or await recent_user_messages(db) >= settings.events_global_limit_hour):
        raise HTTPException(429, "Hay muchos mensajes en este momento. Intenta de nuevo en un rato.")
    db.add(EventMessage(session_id=session.id, role="user", body=message))
    await db.commit()  # visible to the history the agent reads

    result = await run_event_agent(db, session, message)
    session.state_json = json.dumps(result.state, ensure_ascii=False)
    db.add(EventMessage(session_id=session.id, role="assistant", body=result.reply))
    await db.commit()
    return {"session_id": session.id, "reply": result.reply, "ui": result.ui,
            "engine": result.engine, "aviso": VERIFY_NOTE}


@router.post("/select")
async def select_zone(data: SelectIn, db: AsyncSession = Depends(get_db)):
    """UI selector (zone + quantity): same server-validated tools the agent uses."""
    session = await get_or_create_session(db, data.session_id)
    tools = EventTools(db, session)
    sel = await tools.call("calcular_seleccion", {
        "evento_id": data.event_id, "zona_id": data.zone_id, "cantidad": data.quantity})
    ui: list[dict] = []
    if sel.get("ok"):
        await tools.call("registrar_interes", {"evento_id": sel["evento_id"], "zona_id": sel["zona_id"],
                                               "cantidad": sel["cantidad"]})
        link = await tools.call("obtener_enlace_compra", {"evento_id": sel["evento_id"],
                                                          "selection_id": sel["selection_id"]})
        # Remember it so a later "ya pagué" in the chat is tied to this selection.
        session.state_json = json.dumps({**load_state(session), "event_id": sel["evento_id"],
                                         "zone_id": sel["zona_id"], "selection_id": sel["selection_id"]})
        ui = [{"type": "selection", **{k: v for k, v in sel.items() if k != "ok"}},
              {"type": "link", **{k: v for k, v in link.items() if k != "ok"}}]
    await db.commit()
    return {"session_id": session.id, "ok": sel.get("ok", False),
            "error": sel.get("error"), "mensaje": sel.get("mensaje"), "ui": ui}


@router.post("/human")
async def request_human(data: HumanIn, db: AsyncSession = Depends(get_db)):
    session = await get_or_create_session(db, data.session_id)
    res = await EventTools(db, session).call("solicitar_atencion_humana", {"motivo": data.motivo})
    await db.commit()
    return {"session_id": session.id, **res}
