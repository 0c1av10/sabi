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


def _num(value: float) -> str:
    return f"{value:,.2f}".replace(",", "_").replace(".", ",").replace("_", ".")


def rates_of(restaurant: Restaurant) -> tuple[float, float]:
    return restaurant.exchange_rate, restaurant.eur_rate


def fmt_money(usd: float, rate: float, eur_rate: float) -> str:
    bs = usd * rate
    eur = bs / eur_rate if eur_rate else 0.0
    return f"${_num(usd)} · €{_num(eur)} · Bs {_num(bs)}"


def menu_text(items: list[MenuItem], rates: tuple[float, float]) -> str:
    lines = []
    for it in items:
        if it.available:
            lines.append(f"- {it.name} ({it.category}): {fmt_money(it.price, *rates)}")
    return "\n".join(lines)


def summarize_order(order: dict, items_by_name: dict[str, MenuItem], rates: tuple[float, float]) -> tuple[str, float]:
    total = 0.0
    lines = []
    for oi in order.get("items", []):
        mi = items_by_name.get(str(oi.get("name", "")).strip().lower())
        if not mi:
            continue
        qty = int(oi.get("quantity", 1))
        total += mi.price * qty
        extra = f" ({oi['extras']})" if oi.get("extras") else ""
        lines.append(f"• {qty} x {mi.name}{extra} — {fmt_money(mi.price * qty, *rates)}")
    tipo = "Delivery" + (f" a {order.get('address','')}" if order.get("address") else "") \
        if order.get("order_type") == "delivery" else "Retiro en local"
    notes = f"\nNotas: {order['notes']}" if order.get("notes") else ""
    return "\n".join(lines) + f"\n{tipo}{notes}\nTotal: {fmt_money(total, *rates)}", total


def clean_order(order: dict | None, available: dict[str, MenuItem]) -> tuple[dict | None, list[str]]:
    """Keep only available menu items with menu names; return (order, rejected names)."""
    if not isinstance(order, dict):
        return None, []
    items, rejected = [], []
    for oi in order.get("items") or []:
        if not isinstance(oi, dict):
            continue
        name = str(oi.get("name", "")).strip()
        mi = available.get(name.lower())
        if not mi:
            if name:
                rejected.append(name)
            continue
        try:
            qty = max(1, min(int(oi.get("quantity", 1)), 50))
        except (TypeError, ValueError):
            qty = 1
        items.append({"name": mi.name, "quantity": qty,
                      "extras": str(oi.get("extras") or "")[:200],
                      "notes": str(oi.get("notes") or "")[:200]})
    order_type = order.get("order_type")
    return {
        "items": items,
        "order_type": order_type if order_type in ("delivery", "retiro") else None,
        "address": str(order.get("address") or "")[:300],
        "notes": str(order.get("notes") or "")[:500],
    }, rejected


SYSTEM_PROMPT = """Eres Sabi, el agente de ventas por WhatsApp de un restaurante. No eres un bot de preguntas frecuentes: asesoras al cliente como el mejor mesonero de la casa y lo ayudas a elegir.
Reglas:
- Tono cercano y venezolano, tutea al cliente (nunca uses voseo), mensajes cortos para WhatsApp.
- Formato de WhatsApp: negrita con *un asterisco*, nunca **doble** ni títulos markdown.
- Si el cliente duda o pide recomendación, sugiere 1 o 2 opciones concretas del menú con su precio y una razón breve.
- Eres vendedor: cuando el cliente ya eligió su plato y aún no ofreciste complemento, ofrece en ese mismo mensaje un postre o una bebida del menú que combine y que falte en el pedido (con su precio), antes de preguntar delivery o retiro. Solo una vez; si dice que no, no insistas.
- Si algo no está disponible, ofrece la alternativa más parecida del menú.
- Nunca presiones, ni inventes promociones o descuentos.
- Solo vendes ítems del menú provisto. Nunca inventes productos ni precios.
- Los precios se expresan en dólares, euros y bolívares a las tasas del día; usa exactamente los montos del menú.
- Si el cliente pide algo fuera del menú o no sabes algo, dilo y ofrece pasar la conversación al dueño (action=handoff).
- Nunca confirmes un pedido por tu cuenta: el dueño lo aprueba.
- Cuando el pedido esté completo (ítems, cantidades, tipo delivery/retiro, dirección si delivery), repite el resumen y pide validación: action=ask_confirm.
- Si el cliente valida el resumen (sí, ok, confirmo), action=submit_order.
- En "order" manda siempre el pedido completo acumulado hasta ahora (no solo lo nuevo), con el nombre exacto del menú.
- Responde siempre usando la herramienta "responder".
"""

RESPONDER_TOOL = {
    "name": "responder",
    "description": "Envía la respuesta al cliente y el estado del pedido.",
    "input_schema": {
        "type": "object",
        "properties": {
            "reply": {"type": "string", "description": "Texto para el cliente por WhatsApp."},
            "action": {"type": "string", "enum": ["continue", "ask_confirm", "submit_order", "handoff"]},
            "order": {
                "type": ["object", "null"],
                "properties": {
                    "items": {"type": "array", "items": {
                        "type": "object",
                        "properties": {
                            "name": {"type": "string", "description": "Nombre exacto del menú."},
                            "quantity": {"type": "integer", "minimum": 1},
                            "extras": {"type": "string"},
                            "notes": {"type": "string"},
                        },
                        "required": ["name", "quantity"],
                    }},
                    "order_type": {"type": ["string", "null"], "enum": ["delivery", "retiro", None]},
                    "address": {"type": "string"},
                    "notes": {"type": "string"},
                },
                "required": ["items"],
            },
        },
        "required": ["reply", "action"],
    },
}


async def run_agent(db: AsyncSession, restaurant: Restaurant, conversation: Conversation,
                    history: list[tuple[str, str]], incoming: str) -> AgentResult:
    items = (await db.execute(
        select(MenuItem).where(MenuItem.restaurant_id == restaurant.id)
    )).scalars().all()

    if settings.agent_mock_mode or not settings.anthropic_api_key:
        return run_mock_agent(restaurant, items, conversation, incoming)
    return await run_llm_agent(restaurant, items, conversation, history, incoming)


def _llm_messages(history: list[tuple[str, str]], incoming: str) -> list[dict]:
    turns = list(history[-20:]) or [("inbound", incoming)]
    msgs: list[dict] = []
    for direction, body in turns:
        role = "user" if direction == "inbound" else "assistant"
        if msgs and msgs[-1]["role"] == role:
            msgs[-1]["content"] += "\n" + body
        else:
            msgs.append({"role": role, "content": body})
    if msgs[0]["role"] == "assistant":
        msgs.insert(0, {"role": "user", "content": "(inicio de la conversación)"})
    if msgs[-1]["role"] == "assistant":
        msgs.append({"role": "user", "content": incoming})
    return msgs


async def run_llm_agent(restaurant: Restaurant, items: list[MenuItem],
                        conversation: Conversation,
                        history: list[tuple[str, str]], incoming: str) -> AgentResult:
    import anthropic

    state = json.loads(conversation.state_json or "{}")
    rates = rates_of(restaurant)
    available = {i.name.lower(): i for i in items if i.available}
    sold_out = [i.name for i in items if not i.available]
    context = (
        f"\nRestaurante: {restaurant.name}\nHorarios: {restaurant.opening_hours}\n"
        f"Menú disponible hoy:\n{menu_text(items, rates)}\n"
        f"Agotado hoy: {', '.join(sold_out) or 'nada'}\n"
        f"Pedido en curso: {json.dumps(state.get('draft'), ensure_ascii=False)}\n"
        f"Ya ofreciste complemento: {'sí' if state.get('upsell_offered') else 'no'}"
    )

    client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)
    try:
        resp = await client.messages.create(
            model=settings.anthropic_model,
            max_tokens=1000,
            system=SYSTEM_PROMPT + context,
            messages=_llm_messages(history, incoming),
            tools=[RESPONDER_TOOL],
            tool_choice={"type": "tool", "name": "responder"},
        )
    except anthropic.APIError as exc:
        logger.error("Anthropic error: %s", exc)
        return AgentResult(reply="Disculpa, tuve un problema. ¿Me repites tu mensaje en un momento?",
                           state=state)

    data = next((b.input for b in resp.content if b.type == "tool_use"), None)
    if not isinstance(data, dict):
        logger.warning("LLM sin tool_use: %s", resp.content)
        return AgentResult(reply="¿Me repites, por favor?", state=state)

    action = data.get("action") if data.get("action") in (
        "continue", "ask_confirm", "submit_order", "handoff") else "continue"
    reply = str(data.get("reply") or "")
    order, rejected = clean_order(data.get("order"), available)
    if order is None:
        order = state.get("draft")

    if action in ("ask_confirm", "submit_order"):
        complete = bool(order and order["items"] and order["order_type"]
                        and (order["order_type"] != "delivery" or order["address"]))
        if rejected or not complete:
            action = "continue"
            if rejected:
                reply = (f"No tenemos {', '.join(rejected)} en el menú de hoy. "
                         "¿Te recomiendo algo parecido?")
        elif action == "submit_order":
            reply = "¡Perfecto! Tu pedido fue enviado al restaurante para aprobación. Te confirmo enseguida. 🙌"
        else:
            summary, _ = summarize_order(order, available, rates)
            reply = f"Este es tu pedido:\n{summary}\n\n¿Está correcto? Responde 'sí' para enviarlo al restaurante."

    new_state = {**state, "draft": order}
    offered = [i for i in available.values()
               if i.category in _UPSELL_CATEGORIES and i.name.lower() in reply.lower()]
    if order and order["items"] and offered:
        new_state["upsell_offered"] = True
    return AgentResult(reply=reply or "¿Me repites, por favor?", action=action,
                       order=order, state=new_state)


# ---------------- Mock engine (deterministic, no API key needed) ----------------

_YES = r"\b(s[ií]|dale|ok|okay|sumal[oa]|agr[eé]gal[oa]|an[oó]tal[oa]|bueno|perfecto|claro)\b"
_UPSELL_CATEGORIES = ("Bebidas", "Postres")


def pick_upsell(draft_items: list[dict], available: list[MenuItem]) -> MenuItem | None:
    in_order = {d["name"] for d in draft_items}
    cats = {i.category for i in available if i.name in in_order}
    for cat in _UPSELL_CATEGORIES:
        if cat not in cats:
            options = [i for i in available if i.category == cat]
            if options:
                return options[0]
    return None


def recommend(text: str, available: list[MenuItem]) -> list[MenuItem]:
    if re.search(r"compartir|picar|entrada", text):
        pool = [i for i in available if i.category == "Entradas"]
    elif re.search(r"barat|econ[oó]mic", text):
        pool = sorted((i for i in available if i.category == "Platos"), key=lambda i: i.price)
    else:
        pool = [i for i in available if i.category == "Platos"]
    return pool[:2] or available[:2]


_NUM = {"un": 1, "una": 1, "dos": 2, "tres": 3, "cuatro": 4, "cinco": 5, "seis": 6}


def run_mock_agent(restaurant: Restaurant, items: list[MenuItem],
                   conversation: Conversation, incoming: str) -> AgentResult:
    state = json.loads(conversation.state_json or "{}")
    draft = state.get("draft") or {"items": [], "order_type": None, "address": "", "notes": ""}
    text = incoming.lower()
    items_by_name = {i.name.lower(): i for i in items if i.available}
    available = [i for i in items if i.available]
    rates = rates_of(restaurant)

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
        return AgentResult(reply="Este es nuestro menú:\n" + menu_text(available, rates_of(restaurant)),
                           state={**state, "draft": draft})

    if re.search(r"\b(horarios?|abierto|atienden|abren|cierran)\b", text):
        return AgentResult(reply=f"Nuestro horario es: {restaurant.opening_hours}",
                           state={**state, "draft": draft})

    requested = matched_items()

    if not requested and re.search(
            r"recomi[eé]nd|suger|qu[eé] me (das|ofreces)|no s[eé] qu[eé]|compartir|barat|econ[oó]mic", text):
        recs = recommend(text, available)
        lines = "\n".join(f"• {i.name} — {fmt_money(i.price, *rates)}"
                          + (f". {i.description}" if i.description else "") for i in recs)
        return AgentResult(reply=f"Te recomiendo:\n{lines}\n¿Te anoto alguno?",
                           state={**state, "draft": draft})

    sold_out = [i for i in items if not i.available and i.name.lower() in text]
    if sold_out and not requested:
        out = sold_out[0]
        alt = next((i for i in available if i.category == out.category), None)
        if alt:
            state["offer"] = alt.name
            return AgentResult(
                reply=f"Hoy no tenemos {out.name}. Te puedo ofrecer {alt.name} por "
                      f"{fmt_money(alt.price, *rates)}. ¿Te lo anoto?",
                state={**state, "draft": draft})
        return AgentResult(reply=f"Hoy no tenemos {out.name}. ¿Te muestro el menú?",
                           state={**state, "draft": draft})

    offer = state.pop("offer", None)
    if offer and re.search(_YES, text) and not any(r["name"] == offer for r in requested):
        requested.append({"name": offer, "quantity": 1, "extras": "", "notes": ""})

    if re.search(r"\b(delivery|domicilio|env[ií]o|enviar)\b", text):
        draft["order_type"] = "delivery"
    if re.search(r"\b(retiro|recoger|pickup|paso|retirar)\b", text):
        draft["order_type"] = "retiro"
    m = re.search(r"(?:direcci[oó]n|dir(?:ección)?|calle|av(?:enida)?\.?)\s*[:\-]?\s*(.+)", text)
    if draft["order_type"] == "delivery" and m:
        draft["address"] = m.group(1).strip()

    new_items = requested
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
            missing.append("¿Delivery o retiro en el local?")
        elif draft["order_type"] == "delivery" and not draft.get("address"):
            missing.append("¿A qué dirección lo enviamos?")
        upsell = ""
        if not state.get("upsold"):
            extra = pick_upsell(draft["items"], available)
            if extra:
                state["upsold"] = True
                state["offer"] = extra.name
                upsell = f" ¿Le sumamos {extra.name} por {fmt_money(extra.price, *rates)}?"
        got = ", ".join(f'{i["quantity"]} x {i["name"]}' for i in draft["items"])
        if missing:
            return AgentResult(reply=f"Anoté: {got}.{upsell} " + " ".join(missing),
                               state={**state, "draft": draft})
        if upsell:
            return AgentResult(reply=f"Anoté: {got}.{upsell} ¿O lo dejamos así?",
                               state={**state, "draft": draft})
        summary, _ = summarize_order(draft, {i.name.lower(): i for i in items}, rates_of(restaurant))
        return AgentResult(
            reply=f"Este es tu pedido:\n{summary}\n\n¿Está correcto? Responde 'sí' para enviarlo al restaurante.",
            action="ask_confirm", order=draft, state={**state, "stage": "confirming", "draft": draft})

    if re.search(r"\b(dueño|encargado|persona|humano|ayuda)\b", text):
        return AgentResult(reply="Te paso con el dueño, enseguida te atiende. 🙌",
                           action="handoff", state={**state, "draft": draft})

    return AgentResult(
        reply="No tengo eso en el menú. " + (
            f"Si te provoca, te recomiendo {recommend(text, available)[0].name}. " if available else "")
              + "Puedo mostrarte el menú o, si prefieres, te paso con el dueño.",
        state={**state, "draft": draft})
