"""WhatsApp flow to request a boxing class. Deterministic: no LLM, no money.

Steps: name -> level -> preferred day/time -> confirm -> request saved as `solicitada`.
Only an authenticated admin confirms it (routers/events_admin.py); the student is told so.
"""
import json
import re
import unicodedata
import uuid
from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .event_models import EventSession
from .gym_models import ClassRequest, GymProfile
from .models import utcnow
from .whatsapp import digits, send_whatsapp_message

_NAMESPACE = uuid.UUID("0b3a4f2e-7c1d-4e6b-8a55-3e1f9d2c6b11")
FLOW_TTL = timedelta(hours=2)
GYM_INTENT = re.compile(
    r"\b(boxeo|boxear|boxeador\w*|gimnasio|gym|clases?|entrenar|entrenamiento|domicio|rondon|"
    r"reservar\s+(una\s+)?(clase|cupo))\b")
OTHER_TAG = re.compile(r"\[sabi:[a-z0-9-]+\]", re.I)
YES = re.compile(r"^\s*(si|sí|s[ií]i+|ok|dale|listo|confirmo|correcto|claro)\b", re.I)
NO = re.compile(r"^\s*(no|cancelar|cancela|nada|salir)\b", re.I)


def _plain(text: str) -> str:
    nfkd = unicodedata.normalize("NFKD", text or "")
    return "".join(c for c in nfkd if not unicodedata.combining(c)).lower()


def session_id_for(phone: str) -> str:
    return str(uuid.uuid5(_NAMESPACE, "gym:" + digits(phone)))


async def profile(db: AsyncSession) -> GymProfile:
    row = (await db.execute(select(GymProfile).order_by(GymProfile.id))).scalars().first()
    if not row:
        row = GymProfile()
        db.add(row)
        await db.flush()
    return row


async def _state(db: AsyncSession, phone: str) -> tuple[EventSession | None, dict]:
    session = await db.get(EventSession, session_id_for(phone))
    if not session or session.updated_at < utcnow() - FLOW_TTL:
        return session, {}
    try:
        data = json.loads(session.state_json or "{}")
    except ValueError:
        data = {}
    return session, data if isinstance(data, dict) else {}


async def wants_gym(db: AsyncSession, phone: str, body: str) -> bool:
    if OTHER_TAG.search(body):
        return False
    if GYM_INTENT.search(_plain(body)):
        return True
    _, state = await _state(db, phone)
    return bool(state.get("step"))


def _info(p: GymProfile) -> str:
    lines = []
    if p.classes_text:
        lines.append(f"Clases: {p.classes_text}")
    if p.schedule_text:
        lines.append(f"Horarios: {p.schedule_text}")
    if p.membership_text:
        lines.append(f"Mensualidad: {p.membership_text}")
    if p.address:
        lines.append(f"Dónde: {p.address}")
    return "\n".join(lines)


def _level(text: str) -> str:
    t = _plain(text)
    for key, label in (("princip", "principiante"), ("nuev", "principiante"), ("nunca", "principiante"),
                       ("empez", "principiante"), ("inter", "intermedio"), ("avanz", "avanzado"),
                       ("compet", "competitivo")):
        if key in t:
            return label
    return ""


async def _save(db: AsyncSession, session: EventSession, state: dict) -> None:
    session.state_json = json.dumps(state, ensure_ascii=False)
    session.updated_at = utcnow()
    await db.commit()


async def reply_for(db: AsyncSession, phone: str, body: str) -> str:
    p = await profile(db)
    session, state = await _state(db, phone)
    if session is None:
        session = EventSession(id=session_id_for(phone), channel="whatsapp-gym")
        db.add(session)
        await db.flush()
    text = (body or "").strip()[:200]
    step = state.get("step")

    if step and NO.match(text):
        await _save(db, session, {})
        return "Sin problema, cancelé la solicitud. Si quieres reservar otra clase, escríbeme cuando quieras. 🥊"

    if not step:
        info = _info(p)
        msg = (f"¡Hola! 💪 Soy Sabi. Te ayudo a pedir tu clase en *{p.name}*."
               + (f"\n\n{info}" if info else "\n\nEl gimnasio te confirma horarios y cupos cuando reciba tu solicitud."))
        await _save(db, session, {"step": "name"})
        return msg + "\n\nPara empezar, ¿cuál es tu nombre?"

    if step == "name":
        name = re.sub(r"[^\wáéíóúñÁÉÍÓÚÑ .'-]", "", text)[:60].strip()
        if len(name) < 2:
            return "¿Me dices tu nombre para anotarte? 🙂"
        state.update(step="type", name=name)
        await _save(db, session, state)
        options = f" Tenemos: {p.classes_text}." if p.classes_text else ""
        return f"Mucho gusto, {name.split()[0]}.{options} ¿Qué clase te interesa?"

    if step == "type":
        if len(text) < 3:
            return "Dime qué clase te interesa, por ejemplo «boxeo»."
        state.update(step="level", type=text[:60])
        await _save(db, session, state)
        return "¿Qué nivel tienes: principiante, intermedio o avanzado? (si nunca has entrenado, principiante)"

    if step == "level":
        level = _level(text)
        if not level:
            return "Dime si eres principiante, intermedio o avanzado (si nunca has boxeado, principiante)."
        state.update(step="when", level=level)
        await _save(db, session, state)
        return "¿Qué día y a qué hora te gustaría ir? Por ejemplo: «lunes en la tarde»."

    if step == "when":
        if len(text) < 3:
            return "Cuéntame qué día y hora te quedan bien, por ejemplo «miércoles 6 pm»."
        state.update(step="confirm", when=text)
        await _save(db, session, state)
        return (f"Esto es lo que enviaré al gimnasio:\n• Nombre: {state['name']}\n• Clase: {state.get('type', '')}\n"
                f"• Nivel: {state['level']}\n• Preferencia: {text}\n\n¿Lo envío? (sí / no)")

    if step == "confirm":
        if not YES.match(text):
            return "Responde «sí» para enviar la solicitud o «no» para cancelar."
        req = ClassRequest(phone=digits(phone), student_name=state.get("name", ""), level=state.get("level", ""),
                           preferred=f"{state.get('type', '')} — {state.get('when', '')}"[:200])
        db.add(req)
        await _save(db, session, {})
        if p.owner_phone:
            try:
                await send_whatsapp_message(
                    p.owner_phone, f"Nueva solicitud de clase: {req.student_name} ({req.level}), "
                                   f"prefiere {req.preferred}. Confírmala en el panel.")
            except Exception:  # noqa: BLE001 - the request is saved either way
                pass
        extra = f" Si quieres adelantar, también puedes escribir a: {p.contact}." if p.contact else ""
        return ("¡Listo! 🥊 Tu solicitud quedó enviada. Esto no es una reserva todavía: "
                f"{p.name} te confirma el día y la hora por este mismo chat.{extra}")

    await _save(db, session, {})
    return await reply_for(db, phone, body)


async def handle_gym_whatsapp(db: AsyncSession, phone: str, body: str) -> str:
    text = await reply_for(db, phone, body)
    await send_whatsapp_message(phone, text)
    return text
