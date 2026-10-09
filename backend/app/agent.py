"""Sales agent: turns a WhatsApp message into a reply + optional order draft.

Two engines:
- LLM (Anthropic Claude) returning strict JSON.
- Mock: deterministic rules so the full flow is testable without an API key.
"""
import json
import logging
import re
from dataclasses import dataclass, field

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from .config import settings
from .models import Conversation, MenuItem, Restaurant

logger = logging.getLogger("sabi.agent")


@dataclass
class AgentResult:
    reply: str
    action: str = "continue"  # continue | confirm_order | handoff
    order: dict | None = None  # {items:[{name,quantity,extras,notes}], order_type, address, notes}
    state: dict = field(default_factory=dict)


def menu_text(items: list[MenuItem], currency: str) -> str:
    lines = []
    for it in items:
        if it.available:
            lines.append(f"- {it.name} ({it.category}): {currency}{it.price:g}")
    return "\n".join(lines)


def summarize_order(order: dict, items_by_name: dict[str, MenuItem], currency: str) -> tuple[str, float]:
    total = 0.0
    lines = []
    for oi in order.get("items", []):
        mi = items_by_name.get(oi["name"].strip().lower())
        price = mi.price if mi else float(oi.get("unit_price", 0))
        qty = int(oi.get("quantity", 1))
        total += price * qty
        extra = f" ({oi['extras']})" if oi.get("extras") else ""
        lines.append(f"• {qty} x {mi.name if mi else oi['name']}{extra} — {currency}{price*qty:g}")
    tipo = "Delivery" + (f" a {order.get('address','')}" if order.get("address") else "") \
        if order.get("order_type") == "delivery" else "Retiro en local"
    notes = f"\nNotas: {order['notes']}" if order.get("notes") else ""
    return "\n".join(lines) + f"\n{tipo}{notes}\nTotal: {currency}{total:g}", total


SYSTEM_PROMPT = """Eres Sabi, el agente de ventas por WhatsApp de un restaurante.
Reglas:
- Tono cercano, español neutro, mensajes cortos.
- Solo vendes ítems del menú provisto. Nunca inventes productos ni precios.
- Si el cliente pide algo fuera del menú o no sabes algo, dilo y ofrece pasar la conversación al dueño (action=handoff).
- Nunca confirmes un pedido por tu cuenta: el dueño lo aprueba.
- Cuando el pedido esté completo (ítems, cantidades, tipo delivery/retiro, dirección si delivery), repite el resumen y pide validación: action=ask_confirm.
- Si el cliente valida el resumen (sí, ok, confirmo), action=submit_order.
- Responde SOLO con JSON válido:
{"reply": "texto para el cliente", "action": "continue|ask_confirm|submit_order|handoff", "order": {"items": [{"name": "nombre exacto del menú", "quantity": 1, "extras": "", "notes": ""}], "order_type": "delivery|retiro", "address": "", "notes": ""} | null}
"""


async def run_agent(db: AsyncSession, restaurant: Restaurant, conversation: Conversation,
                    history: list[tuple[str, str]], incoming: str) -> AgentResult:
    items = (await db.execute(
        select(MenuItem).where(MenuItem.restaurant_id == restaurant.id)
    )).scalars().all()

    if settings.agent_mock_mode or not settings.anthropic_api_key:
        return run_mock_agent(restaurant, items, conversation, incoming)
    return await run_llm_agent(restaurant, items, conversation, history, incoming)


async def run_llm_agent(restaurant: Restaurant, items: list[MenuItem],
                        conversation: Conversation,
                        history: list[tuple[str, str]], incoming: str) -> AgentResult:
    import anthropic

    state = json.loads(conversation.state_json or "{}")
    menu = menu_text(items, restaurant.currency)
    msgs = [{"role": "user", "content": f"Menú actual:\n{menu}\n\nHorarios: {restaurant.opening_hours}"}]
    for direction, body in history[-20:]:
        msgs.append({"role": "user" if direction == "inbound" else "assistant", "content": body})
    msgs.append({"role": "user", "content":
                 f"Estado guardado: {json.dumps(state, ensure_ascii=False)}\nMensaje del cliente: {incoming}"})

    client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)
    resp = await client.messages.create(
        model=settings.anthropic_model,
        max_tokens=1000,
        system=SYSTEM_PROMPT,
        messages=msgs,
    )
    raw = "".join(b.text for b in resp.content if b.type == "text")
    try:
        data = json.loads(re.search(r"\{.*\}", raw, re.S).group(0))
    except Exception:
        logger.warning("LLM non-JSON reply: %s", raw)
        return AgentResult(reply=raw[:1000] or "¿Me repites, por favor?")

    items_by_name = {i.name.lower(): i for i in items}
    order = data.get("order")
    action = data.get("action", "continue")
    reply = data.get("reply", "")

    if action == "submit_order" and order:
        reply, _ = summarize_order(order, items_by_name, restaurant.currency)
        reply = "¡Perfecto! Tu pedido fue enviado al restaurante para aprobación. Te confirmo enseguida. 🙌"
    elif action == "ask_confirm" and order:
        summary, _ = summarize_order(order, items_by_name, restaurant.currency)
        reply = f"Este es tu pedido:\n{summary}\n\n¿Está correcto? Responde 'sí' para enviarlo al restaurante."

    return AgentResult(reply=reply, action=action, order=order,
                       state={**state, "draft": order or state.get("draft")})


# ---------------- Mock engine (deterministic, no API key needed) ----------------

_NUM = {"un": 1, "una": 1, "dos": 2, "tres": 3, "cuatro": 4, "cinco": 5, "seis": 6}


def run_mock_agent(restaurant: Restaurant, items: list[MenuItem],
                   conversation: Conversation, incoming: str) -> AgentResult:
    state = json.loads(conversation.state_json or "{}")
    draft = state.get("draft") or {"items": [], "order_type": None, "address": "", "notes": ""}
    text = incoming.lower()
    items_by_name = {i.name.lower(): i for i in items if i.available}
    available = [i for i in items if i.available]

    def matched_items() -> list[dict]:
        found = []
        for name, mi in items_by_name.items():
            if name in text:
                qty = 1
                m = re.search(r"(\d+)\s*(?:x|de)?\s*" + re.escape(name), text)
                if m:
                    qty = int(m.group(1))
                else:
                    for w, n in _NUM.items():
                        if re.search(rf"\b{w}\b\s+(?:de\s+)?{re.escape(name)}", text):
                            qty = n
                            break
                found.append({"name": mi.name, "quantity": qty, "extras": "", "notes": ""})
        return found

    # stage: awaiting confirmation of the draft
    if state.get("stage") == "confirming":
        if re.search(r"\b(s[ií]|ok|confirmo|dale|correcto|vale|listo)\b", text):
            return AgentResult(
                reply="¡Perfecto! Tu pedido fue enviado al restaurante para aprobación. Te confirmo enseguida. 🙌",
                action="submit_order", order=draft, state={"stage": "submitted", "draft": draft})
        draft["items"] = []
        state["stage"] = "chat"
        return AgentResult(reply="Entendido, descarté ese pedido. ¿Qué deseas ordenar?",
                           state=state)

    if re.search(r"\b(hola|buenas|buenos d[ií]as|buenas tardes|buenas noches)\b", text) and not draft["items"]:
        return AgentResult(reply=restaurant.welcome_message, state={**state, "draft": draft})

    if re.search(r"\b(men[uú]|carta|qu[eé] tienen|precios?)\b", text):
        return AgentResult(reply="Este es nuestro menú:\n" + menu_text(available, restaurant.currency),
                           state={**state, "draft": draft})

    if re.search(r"\b(horarios?|abierto|atienden|abren|cierran)\b", text):
        return AgentResult(reply=f"Nuestro horario es: {restaurant.opening_hours}",
                           state={**state, "draft": draft})

    if re.search(r"\b(delivery|domicilio|env[ií]o|enviar)\b", text):
        draft["order_type"] = "delivery"
    if re.search(r"\b(retiro|recoger|pickup|paso|retirar)\b", text):
        draft["order_type"] = "retiro"
    m = re.search(r"(?:direcci[oó]n|dir(?:ección)?|calle|av(?:enida)?\.?)\s*[:\-]?\s*(.+)", text)
    if draft["order_type"] == "delivery" and m:
        draft["address"] = m.group(1).strip()

    new_items = matched_items()
    for ni in new_items:
        existing = next((i for i in draft["items"] if i["name"] == ni["name"]), None)
        if existing:
            existing["quantity"] += ni["quantity"]
        else:
            draft["items"].append(ni)
    m = re.search(r"nota[s]?\s*[:\-]?\s*(.+)", text)
    if m:
        draft["notes"] = m.group(1).strip()

    if new_items or draft["items"]:
        missing = []
        if not draft.get("order_type"):
            missing.append("¿delivery o retiro en el local?")
        elif draft["order_type"] == "delivery" and not draft.get("address"):
            missing.append("¿a qué dirección lo enviamos?")
        if missing:
            got = ", ".join(f'{i["quantity"]} x {i["name"]}' for i in draft["items"])
            return AgentResult(reply=f"Anoté: {got}. " + " ".join(missing),
                               state={**state, "draft": draft})
        summary, _ = summarize_order(draft, {i.name.lower(): i for i in items}, restaurant.currency)
        return AgentResult(
            reply=f"Este es tu pedido:\n{summary}\n\n¿Está correcto? Responde 'sí' para enviarlo al restaurante.",
            action="ask_confirm", order=draft, state={**state, "stage": "confirming", "draft": draft})

    if re.search(r"\b(dueño|encargado|persona|humano|ayuda)\b", text):
        return AgentResult(reply="Te paso con el dueño, enseguida te atiende. 🙌",
                           action="handoff", state={**state, "draft": draft})

    return AgentResult(
        reply="No tengo eso en el menú. Puedo mostrarte el menú, horarios o tomar tu pedido. "
              "Si prefieres, te paso con el dueño.",
        state={**state, "draft": draft})
