"""Events assistant core: catalog queries, money, and the seven agent tools.

Every tool validates its arguments with a strict Pydantic model and is authorized
server-side: prices come from the database, and `conversation_id` is injected by the
server (the model can never act on another session). Nothing here confirms a purchase.
"""
import json
import unicodedata
import uuid
from datetime import date, datetime, timedelta, timezone
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from typing import Any
from urllib.parse import urlparse
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import BaseModel, ConfigDict, Field, StrictInt, ValidationError
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from .config import settings
from .event_models import (CURRENCIES, Event, EventActivity, EventMessage,
                           EventPurchaseReport, EventSelection, EventSession,
                           EventZone)
from .models import utcnow

ESTIMATE_NOTE = "subtotal orientativo; cargos adicionales por verificar"
VERIFY_NOTE = ("Precios y disponibilidad se verifican en la plataforma de venta "
               "(TuEntradaWeb) antes de pagar.")
NO_LINK_MESSAGE = "Configura un enlace oficial para habilitar la compra"

MONTHS = ["ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic"]
WEEKDAYS = ["lun", "mar", "mié", "jue", "vie", "sáb", "dom"]


# ----------------------------------------------------------------- money & text

def to_minor(value: Decimal | str | int | float) -> int:
    """Decimal major units -> integer minor units (cents), rounding half up."""
    try:
        d = Decimal(str(value))
    except InvalidOperation as exc:
        raise ValueError("Importe inválido") from exc
    if not d.is_finite():
        raise ValueError("Importe inválido")
    return int((d * 100).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def fmt_minor(amount_minor: int, currency: str) -> str:
    sign = "-" if amount_minor < 0 else ""
    major, cents = divmod(abs(amount_minor), 100)
    num = f"{major:,}".replace(",", ".") + f",{cents:02d}"
    if currency == "USD":
        return f"{sign}${num}"
    if currency == "VES":
        return f"{sign}Bs {num}"
    if currency == "EUR":
        return f"{sign}€{num}"
    return f"{sign}{num} {currency}"


def norm(text: str) -> str:
    """Lowercase and strip accents for forgiving matches (Maracaibo == maracaibo)."""
    nfkd = unicodedata.normalize("NFKD", text or "")
    return "".join(c for c in nfkd if not unicodedata.combining(c)).lower().strip()


def _tz(name: str) -> ZoneInfo | timezone:
    try:
        return ZoneInfo(name)
    except (ZoneInfoNotFoundError, ValueError):
        return timezone(timedelta(hours=-4))


def local_start(event: Event) -> datetime:
    return event.starts_at.replace(tzinfo=timezone.utc).astimezone(_tz(event.timezone))


def fmt_event_date(event: Event) -> str:
    d = local_start(event)
    hour12 = d.hour % 12 or 12
    suffix = "a. m." if d.hour < 12 else "p. m."
    return f"{WEEKDAYS[d.weekday()]} {d.day} {MONTHS[d.month - 1]} {d.year} · {hour12}:{d.minute:02d} {suffix}"


# ------------------------------------------------------------ official link rules

def allowed_hosts() -> set[str]:
    return {h.strip().lower() for h in settings.events_allowed_purchase_hosts.split(",") if h.strip()}


def validate_purchase_url(url: str) -> str:
    """Return a cleaned https URL or raise ValueError. Empty string disables purchase."""
    url = (url or "").strip()
    if not url:
        return ""
    if len(url) > 500:
        raise ValueError("El enlace es demasiado largo")
    parsed = urlparse(url)
    if parsed.scheme != "https" or not parsed.hostname:
        raise ValueError("El enlace oficial debe empezar con https://")
    if parsed.username or parsed.password:
        raise ValueError("El enlace no puede incluir credenciales")
    hosts = allowed_hosts()
    host = parsed.hostname.lower()
    if hosts and not any(host == h or host.endswith("." + h) for h in hosts):
        raise ValueError("El dominio del enlace no está en la lista autorizada")
    return url


# ------------------------------------------------------------------- freshness

def zone_needs_verification(zone: EventZone) -> bool:
    if zone.verified_at is None:
        return True
    return zone.verified_at < utcnow() - timedelta(hours=settings.events_stale_hours)


def zone_public(zone: EventZone) -> dict:
    """Public view of a zone. Never states availability categorically when data is stale."""
    stale = zone_needs_verification(zone)
    if zone.availability == "agotado":
        label = "Agotada según la última verificación"
    elif stale:
        label = "Requiere verificación en TuEntradaWeb"
    elif zone.availability == "disponible":
        label = "Disponible según la última verificación"
    else:
        label = "Por confirmar en TuEntradaWeb"
    return {
        "id": zone.id,
        "nombre": zone.name,
        "precio_referencia": fmt_minor(zone.price_minor, zone.currency),
        "precio_minor": zone.price_minor,
        "moneda": zone.currency,
        "estado_informado": zone.availability,
        "estado": label,
        "requiere_verificacion": stale,
        "recomendable": zone.availability != "agotado",
        "verificado_el": zone.verified_at.isoformat() if zone.verified_at else None,
    }


def purchase_enabled(event: Event) -> bool:
    if event.is_demo or event.status != "publicado" or not event.active:
        return False
    try:
        return bool(validate_purchase_url(event.purchase_url))
    except ValueError:
        return False


def event_public(event: Event, with_zones: bool = True) -> dict:
    data = {
        "id": event.id,
        "slug": event.slug,
        "nombre": event.name,
        "artista": event.artist,
        "ciudad": event.city,
        "recinto": event.venue,
        "fecha": fmt_event_date(event),
        "fecha_iso": event.starts_at.replace(tzinfo=timezone.utc).isoformat(),
        "zona_horaria": event.timezone,
        "descripcion": event.description,
        "imagen": event.image_url,
        "estado": event.status,
        "demo": event.is_demo,
        "compra_habilitada": purchase_enabled(event),
        "actualizado": event.updated_at.isoformat(),
    }
    if with_zones:
        data["zonas"] = [zone_public(z) for z in event.zones]
    return data


# -------------------------------------------------------------------- tool inputs

class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class BuscarEventos(_Strict):
    texto: str | None = Field(None, max_length=100)
    ciudad: str | None = Field(None, max_length=100)
    fecha_desde: date | None = None
    fecha_hasta: date | None = None


class ObtenerEvento(_Strict):
    evento_id: StrictInt


class CalcularSeleccion(_Strict):
    evento_id: StrictInt
    zona_id: StrictInt
    cantidad: StrictInt


class ObtenerEnlaceCompra(_Strict):
    evento_id: StrictInt
    conversation_id: str | None = Field(None, max_length=36)
    selection_id: str | None = Field(None, max_length=36)


class RegistrarInteres(_Strict):
    conversation_id: str | None = Field(None, max_length=36)
    evento_id: StrictInt
    zona_id: StrictInt | None = None
    cantidad: StrictInt | None = None


class SolicitarAtencionHumana(_Strict):
    conversation_id: str | None = Field(None, max_length=36)
    motivo: str = Field(..., min_length=1, max_length=300)


class RegistrarPagoReportado(_Strict):
    conversation_id: str | None = Field(None, max_length=36)
    selection_id: str | None = Field(None, max_length=36)
    referencia_opcional: str | None = Field(None, max_length=160)


TOOL_MODELS: dict[str, type[BaseModel]] = {
    "buscar_eventos": BuscarEventos,
    "obtener_evento": ObtenerEvento,
    "calcular_seleccion": CalcularSeleccion,
    "obtener_enlace_compra": ObtenerEnlaceCompra,
    "registrar_interes": RegistrarInteres,
    "solicitar_atencion_humana": SolicitarAtencionHumana,
    "registrar_pago_reportado": RegistrarPagoReportado,
}

TOOL_DESCRIPTIONS = {
    "buscar_eventos": "Busca eventos publicados en el catálogo local por texto, ciudad y rango de fechas (YYYY-MM-DD). Devuelve hasta 3.",
    "obtener_evento": "Devuelve un evento con sus zonas, precios de referencia y estado informado.",
    "calcular_seleccion": "Calcula en el backend el subtotal orientativo de una zona y cantidad. No es una reserva.",
    "obtener_enlace_compra": "Devuelve el enlace oficial de compra (con registro de clic) si está habilitado.",
    "registrar_interes": "Registra el interés del usuario en un evento, zona o cantidad.",
    "solicitar_atencion_humana": "Pide que una persona del equipo atienda la conversación.",
    "registrar_pago_reportado": "Registra que el usuario DICE haber pagado. No confirma ningún pago.",
}


def llm_tool_specs() -> list[dict]:
    """Anthropic tool definitions. `conversation_id` is hidden: the server injects it."""
    specs = []
    for name, model in TOOL_MODELS.items():
        schema = model.model_json_schema()
        schema.pop("title", None)
        props = schema.get("properties", {})
        props.pop("conversation_id", None)
        schema["required"] = [r for r in schema.get("required", []) if r != "conversation_id"]
        schema["additionalProperties"] = False
        specs.append({"name": name, "description": TOOL_DESCRIPTIONS[name], "input_schema": schema})
    return specs


# ------------------------------------------------------------------------ tools

def _err(code: str, message: str) -> dict:
    return {"ok": False, "error": code, "mensaje": message}


async def get_or_create_session(db: AsyncSession, session_id: str | None,
                                channel: str = "web") -> EventSession:
    if session_id:
        try:
            uuid.UUID(session_id)
        except ValueError:
            session_id = None
    if session_id:
        existing = await db.get(EventSession, session_id)
        if existing:
            return existing
    session = EventSession(id=str(uuid.uuid4()), channel=channel)
    db.add(session)
    await db.flush()
    return session


class EventTools:
    """Tool executor bound to one server-trusted session."""

    def __init__(self, db: AsyncSession, session: EventSession):
        self.db = db
        self.session = session
        self.calls = 0

    async def call(self, name: str, args: dict[str, Any] | None) -> dict:
        model = TOOL_MODELS.get(name)
        if model is None:
            return _err("herramienta_desconocida", "Esa herramienta no existe.")
        if self.calls >= settings.events_max_tool_calls:
            return _err("limite_herramientas", "Se alcanzó el límite de consultas en este turno.")
        self.calls += 1
        raw = dict(args or {})
        if "conversation_id" in model.model_fields:
            raw["conversation_id"] = self.session.id  # never trust the model/user for this
        try:
            parsed = model.model_validate(raw)
        except ValidationError as exc:
            fields = ", ".join(sorted({str(e["loc"][0]) for e in exc.errors() if e["loc"]}))
            return _err("argumentos_invalidos", f"Argumentos inválidos: {fields or 'revisa los datos'}.")
        return await getattr(self, f"_{name}")(parsed)

    # -- helpers
    async def _load_event(self, event_id: int) -> Event | None:
        return (await self.db.execute(
            select(Event).where(Event.id == event_id).options(selectinload(Event.zones))
        )).scalar_one_or_none()

    async def _visible_event(self, event_id: int) -> Event | None:
        ev = await self._load_event(event_id)
        if ev is None or not ev.active or ev.status == "borrador":
            return None  # drafts and deactivated events do not exist for the public
        return ev

    def _log(self, kind: str, event_id: int | None = None, zone_id: int | None = None,
             selection_id: str | None = None, detail: str = "") -> EventActivity:
        row = EventActivity(session_id=self.session.id, event_id=event_id, zone_id=zone_id,
                            selection_id=selection_id, kind=kind, detail=detail[:500])
        self.db.add(row)
        return row

    # -- tools
    async def _buscar_eventos(self, a: BuscarEventos) -> dict:
        events = (await self.db.execute(
            select(Event).where(Event.status == "publicado", Event.active.is_(True))
            .options(selectinload(Event.zones)).order_by(Event.starts_at)
        )).scalars().all()
        now = utcnow()
        out = []
        for ev in events:
            if ev.starts_at < now:
                continue
            local_day = local_start(ev).date()
            if a.ciudad and norm(a.ciudad) not in norm(ev.city):
                continue
            if a.fecha_desde and local_day < a.fecha_desde:
                continue
            if a.fecha_hasta and local_day > a.fecha_hasta:
                continue
            if a.texto:
                hay = norm(" ".join([ev.name, ev.artist, ev.venue, ev.description, ev.city]))
                if not all(tok in hay for tok in norm(a.texto).split()):
                    continue
            out.append(event_public(ev))
            if len(out) == 3:
                break
        return {"ok": True, "total": len(out), "eventos": out, "aviso": VERIFY_NOTE}

    async def _obtener_evento(self, a: ObtenerEvento) -> dict:
        ev = await self._visible_event(a.evento_id)
        if ev is None:
            return _err("evento_no_encontrado", "No encontré ese evento en el catálogo.")
        data = event_public(ev)
        data["a_la_venta"] = ev.status == "publicado" and ev.starts_at >= utcnow()
        return {"ok": True, "evento": data, "aviso": VERIFY_NOTE}

    async def _calcular_seleccion(self, a: CalcularSeleccion) -> dict:
        limit = settings.events_max_quantity
        if a.cantidad < 1 or a.cantidad > limit:
            return _err("cantidad_invalida", f"La cantidad debe ser un número entero entre 1 y {limit}.")
        ev = await self._visible_event(a.evento_id)
        if ev is None:
            return _err("evento_no_encontrado", "No encontré ese evento en el catálogo.")
        if ev.status != "publicado" or ev.starts_at < utcnow():
            return _err("evento_no_disponible", "Ese evento ya no está a la venta.")
        zone = next((z for z in ev.zones if z.id == a.zona_id), None)
        if zone is None:
            return _err("zona_invalida", "Esa zona no pertenece a ese evento.")
        if zone.availability == "agotado":
            return _err("zona_agotada", f"La zona {zone.name} figura como agotada.")
        subtotal = zone.price_minor * a.cantidad  # integer minor units: no float math
        warnings = []
        if zone_needs_verification(zone):
            warnings.append("Los datos de esta zona no se han verificado recientemente; confírmalos en TuEntradaWeb.")
        if zone.availability == "por_confirmar":
            warnings.append("La disponibilidad de esta zona está por confirmar.")
        sel = EventSelection(
            id=str(uuid.uuid4()), session_id=self.session.id, event_id=ev.id, zone_id=zone.id,
            quantity=a.cantidad, unit_price_minor=zone.price_minor, subtotal_minor=subtotal,
            currency=zone.currency)
        self.db.add(sel)
        self._log("selection", ev.id, zone.id, sel.id, f"cantidad={a.cantidad}")
        await self.db.flush()
        return {
            "ok": True,
            "selection_id": sel.id,
            "evento": ev.name,
            "evento_id": ev.id,
            "zona": zone.name,
            "zona_id": zone.id,
            "cantidad": a.cantidad,
            "precio_unitario": fmt_minor(zone.price_minor, zone.currency),
            "subtotal": fmt_minor(subtotal, zone.currency),
            "subtotal_minor": subtotal,
            "moneda": zone.currency,
            "nota": ESTIMATE_NOTE,
            "advertencias": warnings,
            "aviso": "Esto no es una reserva. " + VERIFY_NOTE,
        }

    async def _obtener_enlace_compra(self, a: ObtenerEnlaceCompra) -> dict:
        ev = await self._visible_event(a.evento_id)
        if ev is None:
            return _err("evento_no_encontrado", "No encontré ese evento en el catálogo.")
        if not purchase_enabled(ev):
            return {"ok": True, "habilitado": False, "mensaje": NO_LINK_MESSAGE}
        selection_id = None
        if a.selection_id:
            sel = await self.db.get(EventSelection, a.selection_id)
            if sel and sel.session_id == self.session.id and sel.event_id == ev.id:
                selection_id = sel.id
        path = f"/api/events/go/{ev.id}?c={self.session.id}"
        if selection_id:
            path += f"&s={selection_id}"
        return {
            "ok": True,
            "habilitado": True,
            "ruta": path,
            "texto_boton": "Ver disponibilidad y comprar en TuEntradaWeb",
            "aviso": ("Al abrir el enlace sales de Sabi. El pago se hace en la plataforma externa y "
                      "allí se verifica la disponibilidad; abrirlo no reserva nada."),
        }

    async def _registrar_interes(self, a: RegistrarInteres) -> dict:
        ev = await self._visible_event(a.evento_id)
        if ev is None:
            return _err("evento_no_encontrado", "No encontré ese evento en el catálogo.")
        if a.zona_id is not None and not any(z.id == a.zona_id for z in ev.zones):
            return _err("zona_invalida", "Esa zona no pertenece a ese evento.")
        if a.cantidad is not None and not (1 <= a.cantidad <= settings.events_max_quantity):
            return _err("cantidad_invalida",
                        f"La cantidad debe ser un entero entre 1 y {settings.events_max_quantity}.")
        detail = f"cantidad={a.cantidad}" if a.cantidad else ""
        dup = (await self.db.execute(select(EventActivity.id).where(
            EventActivity.session_id == self.session.id, EventActivity.kind == "interest",
            EventActivity.event_id == ev.id, EventActivity.zone_id == a.zona_id,
            EventActivity.detail == detail))).first()
        if not dup:
            self._log("interest", ev.id, a.zona_id, None, detail)
            await self.db.flush()
        return {"ok": True, "mensaje": "Interés registrado. No es una reserva."}

    async def _solicitar_atencion_humana(self, a: SolicitarAtencionHumana) -> dict:
        self._log("human_request", None, None, None, a.motivo)
        await self.db.flush()
        return {"ok": True, "mensaje": ("Dejé tu solicitud para el equipo. No puedo asegurarte "
                                        "cuándo te contactarán.")}

    async def _registrar_pago_reportado(self, a: RegistrarPagoReportado) -> dict:
        event_id = None
        selection_id = None
        if a.selection_id:
            sel = await self.db.get(EventSelection, a.selection_id)
            if not sel or sel.session_id != self.session.id:
                return _err("seleccion_invalida", "No encontré esa selección en esta conversación.")
            selection_id, event_id = sel.id, sel.event_id
        report = EventPurchaseReport(
            session_id=self.session.id, selection_id=selection_id, event_id=event_id,
            user_reference=(a.referencia_opcional or "").strip(), status="reported")
        self.db.add(report)
        self._log("payment_reported", event_id, None, selection_id, a.referencia_opcional or "")
        await self.db.flush()
        return {
            "ok": True,
            "estado": "pago_reportado",
            "mensaje": ("Registré que reportaste un pago. Esto NO confirma el pago ni la compra: "
                        "una persona del equipo debe verificarlo."),
        }


# ------------------------------------------------------------------ chat plumbing

async def recent_user_messages(db: AsyncSession, session_id: str | None = None) -> int:
    q = select(func.count(EventMessage.id)).where(
        EventMessage.role == "user", EventMessage.created_at >= utcnow() - timedelta(hours=1))
    if session_id:
        q = q.where(EventMessage.session_id == session_id)
    return (await db.execute(q)).scalar_one()


def load_state(session: EventSession) -> dict:
    try:
        data = json.loads(session.state_json or "{}")
        return data if isinstance(data, dict) else {}
    except ValueError:
        return {}
