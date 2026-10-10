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
        mi = items_by_name.get(oi["name"].strip().lower())
        price = mi.price if mi else float(oi.get("unit_price", 0))
        qty = int(oi.get("quantity", 1))
        total += price * qty
        extra = f" ({oi['extras']})" if oi.get("extras") else ""
        lines.append(f"• {qty} x {mi.name if mi else oi['name']}{extra} — {fmt_money(price * qty, *rates)}")
    tipo = "Delivery" + (f" a {order.get('address','')}" if order.get("address") else "") \
        if order.get("order_type") == "delivery" else "Retiro en local"
    notes = f"\nNotas: {order['notes']}" if order.get("notes") else ""
    return "\n".join(lines) + f"\n{tipo}{notes}\nTotal: {fmt_money(total, *rates)}", total


SYSTEM_PROMPT = """Eres Sabi, el agente de ventas por WhatsApp de un restaurante. No eres un bot de preguntas frecuentes: asesoras al cliente como el mejor mesonero de la casa y lo ayudas a elegir.
Reglas:
- Tono cercano, español neutro, mensajes cortos.
- Si el cliente duda o pide recomendación, sugiere 1 o 2 opciones concretas del menú con su precio y una razón breve.
- Antes de cerrar el pedido, ofrece una sola vez un complemento que falte (bebida o postre). Si dice que no, no insistas.
- Si algo no está disponible, ofrece la alternativa más parecida del menú.
- Nunca presiones, ni inventes promociones o descuentos.
- Solo vendes ítems del menú provisto. Nunca inventes productos ni precios.
- Los precios se expresan en dólares, euros y bolívares a las tasas del día; usa exactamente los montos del menú.
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
    menu = menu_text(items, rates_of(restaurant))
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
        reply, _ = summarize_order(order, items_by_name, rates_of(restaurant))
        reply = "¡Perfecto! Tu pedido fue enviado al restaurante para aprobación. Te confirmo enseguida. 🙌"
    elif action == "ask_confirm" and order:
        summary, _ = summarize_order(order, items_by_name, rates_of(restaurant))
        reply = f"Este es tu pedido:\n{summary}\n\n¿Está correcto? Responde 'sí' para enviarlo al restaurante."

    return AgentResult(reply=reply, action=action, order=order,
                       state={**state, "draft": order or state.get("draft")})


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
