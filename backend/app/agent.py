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

from . import delivery
from .config import settings
from .models import Conversation, Customer, MenuItem, Restaurant

logger = logging.getLogger("sabi.agent")


@dataclass
class AgentResult:
    reply: str
    action: str = "continue"  # continue | confirm_order | handoff
    order: dict | None = None  # {items:[{name,quantity,extras,notes}], order_type, address, notes}
    state: dict = field(default_factory=dict)


def _num(value: float) -> str:
    return f"{value:,.2f}".replace(",", "_").replace(".", ",").replace("_", ".")


def rates_of(restaurant: Restaurant) -> tuple[float, float, str]:
    return restaurant.exchange_rate, restaurant.eur_rate, restaurant.currency


def fmt_money(amount: float, rate: float, _eur_rate: float, currency: str = "USD") -> str:
    if currency == "EUR":
        return f"€{_num(amount)}"
    return f"${_num(amount)} · Bs {_num(amount * rate)}"


def menu_text(items: list[MenuItem], rates: tuple[float, float, str], *, descriptions: bool = True) -> str:
    lines = []
    for it in items:
        if it.available:
            line = f"- {it.name} ({it.category}): {fmt_money(it.price, *rates)}"
            if descriptions and it.description:
                desc = " ".join(it.description.split())
                if desc:
                    line += f" — {desc[:240]}" + ("…" if len(desc) > 240 else "")
            lines.append(line)
    return "\n".join(lines)


def delivery_context(restaurant: Restaurant, rates: tuple[float, float, str]) -> str:
    return delivery.describe(restaurant, lambda v: fmt_money(v, *rates))


def delivery_fee_for(restaurant: Restaurant, order: dict) -> float:
    return delivery.fee_for(restaurant, order.get("order_type"), order.get("delivery_zone") or "")


def summarize_order(order: dict, items_by_name: dict[str, MenuItem], rates: tuple[float, float, str],
                    delivery_fee: float = 0.0) -> tuple[str, float]:
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
    zone = f" ({order['delivery_zone']})" if order.get("delivery_zone") else ""
    tipo = "Delivery" + zone + (f" a {order.get('address','')}" if order.get("address") else "") \
        if order.get("order_type") == "delivery" else "Retiro en local"
    notes = f"\nNotas: {order['notes']}" if order.get("notes") else ""
    fee_line = ""
    if delivery_fee and order.get("order_type") == "delivery":
        total += delivery_fee
        fee_line = f"\n• Delivery{zone} — {fmt_money(delivery_fee, *rates)}"
    return "\n".join(lines) + fee_line + f"\n{tipo}{notes}\nTotal: {fmt_money(total, *rates)}", total


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
        "delivery_zone": str(order.get("delivery_zone") or "")[:100],
        "notes": str(order.get("notes") or "")[:500],
        "payment_method": str(order.get("payment_method") or "")[:40],
        "payment_reference": str(order.get("payment_reference") or "")[:160],
    }, rejected


SYSTEM_PROMPT = """Eres Sabi, un asistente personal que ayuda a consultar distintos comercios. No eres empleado ni representante del restaurante y nunca digas «Sabi de [local]». No eres un bot de preguntas frecuentes: asesoras al cliente como el mejor mesonero de la casa y lo ayudas a elegir. Hablas en español venezolano, ameno y cercano. No te presentes cada vez como "el asistente de" un local: preséntate solo como Sabi y atiende con calidez; si el cliente duda o pregunta qué hay, recomiéndale platos concretos del menú.
Reglas:
- Tono cercano y venezolano, tutea al cliente (nunca uses voseo), mensajes cortos para WhatsApp.
- No incluyas emojis en el texto. Las reacciones nativas se gestionan fuera de tu respuesta.
- Formato de WhatsApp: negrita con *un asterisco*, nunca **doble** ni títulos markdown.
- Si el cliente duda o pide recomendación, sugiere 1 o 2 opciones concretas del menú con su precio y una razón breve.
- Eres vendedor: cuando el cliente ya eligió su plato y aún no ofreciste complemento, ofrece en ese mismo mensaje un postre o una bebida del menú que combine y que falte en el pedido (con su precio), antes de preguntar delivery o retiro. Solo una vez; si dice que no, no insistas.
- Si algo no está disponible, ofrece la alternativa más parecida del menú.
- Nunca presiones, ni inventes promociones o descuentos.
- Solo vendes ítems del menú provisto. Nunca inventes productos ni precios.
{price_rules}
- Si no sabes algo, di qué dato falta. Nunca ofrezcas ni afirmes pasar la conversación al dueño: no hay un canal humano verificado. No uses action=handoff.
- Si el pedido es delivery, pregunta la zona cuando hay zonas, e informa el costo de delivery del contexto antes de pedir la confirmación. Nunca inventes montos ni zonas distintas a las del contexto.
- Nunca confirmes un pedido por tu cuenta: el dueño lo aprueba. No afirmes que se envió o recibió ni prometas una aprobación o un plazo. Elegir método de pago no prueba pago. Una referencia es una declaración no verificada.
- Cuando el pedido esté completo (ítems, cantidades, tipo delivery/retiro, dirección si delivery), repite el resumen y pide validación: action=ask_confirm.
- Si el cliente valida el resumen (sí, ok, confirmo), action=submit_order.
- Antes de enviarlo al restaurante, pregunta cómo va a pagar: pago móvil, Zelle, transferencia o efectivo al retirar.
- Si el cliente ya indicó un método de pago, inclúyelo en order.payment_method. El comercio verifica el pago antes de aprobar.
- En "order" manda siempre el pedido completo acumulado hasta ahora (no solo lo nuevo), con el nombre exacto del menú.
- Si el cliente dice «ese», «esa» o similar refiriéndose a varias opciones que acabas de ofrecer, pregunta cuál de ellas quiere; nunca elijas una por tu cuenta. Conserva lo demás del pedido (tipo, dirección, notas).
- Si pide una fecha u hora de entrega («pídelo mañana a las 9 am»), guárdala textual en order.notes y confírmala en tu resumen.
- Responde siempre usando la herramienta "responder".
"""

USD_PRICE_RULES = """- Los precios se expresan solo en dólares y bolívares a las tasas del día. Nunca muestres euros en WhatsApp.
- Mantén los precios compactos en una sola línea: "$X · Bs Y"."""
EUR_PRICE_RULES = "- Expresa los precios en euros tal como aparecen en el contexto: €X. No los conviertas a dólares ni bolívares."

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
                    "delivery_zone": {"type": "string", "description": "Zona de delivery elegida, nombre exacto de las zonas del contexto; vacío si no hay."},
                    "notes": {"type": "string"},
                    "payment_method": {"type": "string"},
                    "payment_reference": {"type": "string"},
                },
                "required": ["items"],
            },
        },
        "required": ["reply", "action"],
    },
}


def grounded_retry(restaurant: Restaurant) -> str:
    """Fallback when the model returns nothing usable: stay helpful and specific instead
    of a bare "¿Me repites?" that reads as amnesia and makes the client repeat themselves."""
    return (f"No te entendí bien. ¿Qué se te antoja de {restaurant.name}? "
            "Puedo mostrarte el menú o recomendarte algo.")


def guard_representation(result: AgentResult,restaurant: Restaurant) -> AgentResult:
    """No verified human escalation destination exists in this chat path."""
    result.reply=re.sub(r'(?i)soy Sabi de\s+'+re.escape(restaurant.name), 'Soy Sabi',result.reply)
    if result.action=='handoff' or re.search(r'(?i)(?:(?:te|le) (?:paso|pase|pasaré|pasare|puedo pasar)|pasar (?:la|esta) conversaci[oó]n).{0,60}(?:due[nñ]o|encargad[oa]|humano)',result.reply):
        result.action='continue'
        result.reply=f'No tengo ese dato verificado de {restaurant.name} ni un canal humano confirmado para consultarlo por ti. Puedo ayudarte con la información que sí está registrada.'
    return result


async def run_agent(db: AsyncSession, restaurant: Restaurant, conversation: Conversation,
                    history: list[tuple[str, str]], incoming: str) -> AgentResult:
    items = (await db.execute(
        select(MenuItem).where(MenuItem.restaurant_id == restaurant.id)
    )).scalars().all()

    if re.search(r'\b(horarios?|abierto|atienden|abren|cierran)\b',incoming,re.I):
        hours=(restaurant.opening_hours or '').strip()
        return AgentResult(reply=(f'El horario registrado de {restaurant.name} es: {hours}. Confírmalo con el local antes de ir.' if hours else f'No tengo un horario verificado de {restaurant.name}. No tengo un contacto humano confirmado para consultarlo por ti.'),state=json.loads(conversation.state_json or '{}'))
    if settings.agent_mock_mode or not settings.anthropic_api_key:
        return guard_representation(run_mock_agent(restaurant, items, conversation, incoming, history),restaurant)
    customer = await db.get(Customer, conversation.customer_id)
    from . import memory
    contact = await memory.get(db, customer.phone) if customer else None
    known = memory.display_name((contact.name if contact else None) or (customer.name if customer else ""))
    general_topic = (contact.last_topic if contact else '') or ''
    return guard_representation(await run_llm_agent(restaurant, items, conversation, history, incoming, known,
                                                    general_topic),restaurant)


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
                        history: list[tuple[str, str]], incoming: str,
                        customer_name: str = "", general_topic: str = "") -> AgentResult:
    import anthropic

    state = json.loads(conversation.state_json or "{}")
    rates = rates_of(restaurant)
    available = {i.name.lower(): i for i in items if i.available}
    sold_out = [i.name for i in items if not i.available]
    context = (
        f"\nRestaurante: {restaurant.name}\nHorarios: {restaurant.opening_hours}\n"
        f"{delivery_context(restaurant, rates)}\n"
        f"Menú disponible hoy:\n{menu_text(items, rates)}\n"
        f"Agotado hoy: {', '.join(sold_out) or 'nada'}\n"
        f"Pedido en curso: {json.dumps(state.get('draft'), ensure_ascii=False)}\n"
        f"Ya ofreciste complemento: {'sí' if state.get('upsell_offered') else 'no'}"
    )
    if customer_name:
        context += (f"\nEl cliente se llama {customer_name}: dirígete a él por su nombre con naturalidad, "
                    "sin repetirlo en cada mensaje.")
    inbound_count = sum(1 for direction, _ in history if direction == "inbound")
    if inbound_count <= 1:
        context += ("\nEste es el primer mensaje del cliente con este local: puede venir de una "
                    "conversación general con Sabi (recomendaciones de locales u otro tema). "
                    "Interpreta mensajes cortos o ambiguos («ese», «y nacional?») a la luz del menú "
                    "y pregunta con naturalidad qué se le antoja; nunca contestes pidiendo que repita "
                    "sin ofrecer nada.")
    if general_topic:
        context += (f"\nÚltimo tema de la conversación general con Sabi: {general_topic}. "
                    "Úsalo para entender referencias cortas; no lo repitas literalmente al cliente.")

    client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)
    try:
        resp = await client.messages.create(
            model=settings.anthropic_model,
            max_tokens=1000,
            system=SYSTEM_PROMPT.format(price_rules=EUR_PRICE_RULES if restaurant.currency == "EUR" else USD_PRICE_RULES)
            + context,
            messages=_llm_messages(history, incoming),
            tools=[RESPONDER_TOOL],
            tool_choice={"type": "auto"},
        )
    except anthropic.APIError as exc:
        logger.error("Anthropic error: %s", exc)
        return AgentResult(reply="Disculpa, tuve un problema. ¿Me repites tu mensaje en un momento?",
                           state=state)

    data = next((b.input for b in resp.content if b.type == "tool_use"), None)
    if not isinstance(data, dict):
        raw = "".join(b.text for b in resp.content if b.type == "text").strip()
        match = re.search(r"\{.*\}", raw, re.S)
        try:
            data = json.loads(match.group(0)) if match else None
        except ValueError:
            data = None
        if not isinstance(data, dict):
            logger.warning("LLM sin tool_use: %s", raw[:500])
            data = {"reply": raw[:1000], "action": "continue"}

    action = data.get("action") if data.get("action") in (
        "continue", "ask_confirm", "submit_order", "handoff") else "continue"
    reply = str(data.get("reply") or "")
    order, rejected = clean_order(data.get("order"), available)
    if order is None:
        order = state.get("draft")
    zones = delivery.zones_of(restaurant)
    if order is not None and zones:
        chosen = delivery.find_zone(zones, order.get("delivery_zone") or "") \
            or delivery.find_zone(zones, order.get("address") or "")
        order["delivery_zone"] = chosen["name"] if chosen else ""

    if action in ("ask_confirm", "submit_order"):
        complete = bool(order and order["items"] and order["order_type"]
                        and (order["order_type"] != "delivery"
                             or (order["address"] and (not zones or order.get("delivery_zone")))))
        if rejected or not complete:
            action = "continue"
            if rejected:
                reply = (f"No tenemos {', '.join(rejected)} en el menú de hoy. "
                         "¿Te recomiendo algo parecido?")
        elif action == "submit_order":
            if not order.get("payment_method"):
                action = "continue"
                reply = ("Perfecto. Antes de enviarlo al restaurante, ¿cómo vas a pagar? "
                         "Puedes usar pago móvil, Zelle, transferencia o efectivo al retirar.")
            else:
                reply = "Tu solicitud está pendiente de registro. Aún no hay confirmación del restaurante ni del pago."
        else:
            summary, _ = summarize_order(order, available, rates, delivery_fee_for(restaurant, order))
            reply = f"Este es tu pedido:\n{summary}\n\n¿Está correcto? Responde 'sí' para enviarlo al restaurante."

    new_state = {**state, "draft": order}
    offered = [i for i in available.values()
               if i.category in _UPSELL_CATEGORIES and i.name.lower() in reply.lower()]
    if order and order["items"] and offered:
        new_state["upsell_offered"] = True
    return AgentResult(reply=reply or grounded_retry(restaurant), action=action,
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
                   conversation: Conversation, incoming: str,
                   history: list[tuple[str, str]] | None = None) -> AgentResult:
    state = json.loads(conversation.state_json or "{}")
    draft = state.get("draft") or {
        "items": [], "order_type": None, "address": "", "delivery_zone": "", "notes": "",
        "payment_method": "", "payment_reference": "",
    }
    text = incoming.lower()
    items_by_name = {i.name.lower(): i for i in items if i.available}
    available = [i for i in items if i.available]
    rates = rates_of(restaurant)
    zones = delivery.zones_of(restaurant)

    def matched_items() -> list[dict]:
        words = "|".join(_NUM)
        quantity = rf"(?:(?P<number>\d+)\s*(?:x|de)?\s*|(?P<word>{words})\s+(?:de\s+)?)?"
        matches = []
        for name, item in items_by_name.items():
            plural = r"(?:es|s)?" if name[-1:].isalpha() else ""
            pattern = rf"(?<!\w){quantity}(?P<item>{re.escape(name)}{plural})(?!\w)"
            for match in re.finditer(pattern, text):
                qty = int(match["number"]) if match["number"] else _NUM.get(match["word"], 1)
                matches.append((*match.span("item"), item.name, qty))

        selected: list[tuple[int, int, str, int]] = []
        for start, end, name, qty in sorted(matches, key=lambda hit: (-len(hit[2]), hit[0])):
            if not any(start < stop and end > begin for begin, stop, _, _ in selected):
                selected.append((start, end, name, qty))

        quantities: dict[str, int] = {}
        for _, _, name, qty in sorted(selected):
            quantities[name] = quantities.get(name, 0) + qty
        return [{"name": name, "quantity": qty, "extras": "", "notes": ""} for name, qty in quantities.items()]

    asks_delivery_fee = (
        bool(zones) and re.search(r"\b(?:delivery|domicilio|env[ií]o)\b", text) is not None
        and re.search(r"\b(?:cu[aá]nto|cuesta|costo|precio|tarifa)\b", text) is not None
    )
    requested = None
    if asks_delivery_fee:
        order_intent = re.search(
            r"(?<!\bno )\b(?:(?:quiero|quisiera)(?!\s+(?:saber|conocer|consultar|preguntar)\b)|"
            r"dame|p[ií]de|p[ií]deme|agrega|agr[eé]game|a[nñ]ade|a[nñ][aá]deme|"
            r"m[aá]ndame|env[ií]ame|ponme|anota|an[oó]tame|tr[aá]eme)\b", text,
        )
        requested = matched_items() if order_intent else []
    if asks_delivery_fee and not requested:
        fees = "\n".join(
            f"• {zone['name']}: " + (fmt_money(zone["fee"], *rates) if zone["fee"] else "gratis")
            for zone in zones
        )
        return AgentResult(reply=f"El costo del delivery depende de la zona:\n{fees}", state=state)

    if re.search(r"\bqu[eé]\s+(?:(?:es\s+lo\s+que)\s+)?(?:incluye|trae|lleva|contiene)\b", text):
        question = delivery.plain(text)
        match = max(
            (i for i in available if re.search(rf"(?<!\w){re.escape(delivery.plain(i.name))}(?!\w)", question)),
            key=lambda i: len(i.name),
            default=None,
        )
        if match:
            return AgentResult(reply=(f"*{match.name}* — {fmt_money(match.price, *rates)}. {match.description}"
                                      if match.description else f"No tengo los ingredientes de {match.name} registrados."),
                               state=state)

    # stage: awaiting confirmation of the draft
    if state.get("stage") == "confirming":
        if re.search(r"\b(s[ií]|ok|confirmo|dale|correcto|vale|listo)\b", text):
            return AgentResult(
                reply=("Perfecto. ¿Cómo vas a pagar? Puedes usar pago móvil, Zelle, "
                       "transferencia o efectivo al retirar."),
                state={"stage": "payment", "draft": draft})
        draft["items"] = []
        state["stage"] = "chat"
        return AgentResult(reply="Entendido, descarté ese pedido. ¿Qué deseas ordenar?",
                           state=state)

    if state.get("stage") == "payment":
        methods = (
            ("pago móvil", "pago_movil"), ("pago movil", "pago_movil"),
            ("zelle", "zelle"), ("transferencia", "transferencia"),
            ("efectivo", "efectivo"),
        )
        chosen = next((value for label, value in methods if label in text), "")
        if chosen:
            draft["payment_method"] = chosen
            ref = re.search(r"(?:referencia|ref\.?|comprobante)\s*[:#-]?\s*([a-z0-9-]+)", text)
            if ref:
                draft["payment_reference"] = ref.group(1)
            return AgentResult(
                reply="Tu solicitud está pendiente de registro. Aún no hay confirmación del restaurante ni del pago.",
                action="submit_order", order=draft,
                state={"stage": "submitted", "draft": draft})
        return AgentResult(
            reply="Indícame cómo vas a pagar: pago móvil, Zelle, transferencia o efectivo al retirar.",
            state={"stage": "payment", "draft": draft})

    if re.search(r"\b(hola|buenas|buenos d[ií]as|buenas tardes|buenas noches)\b", text) and not draft["items"]:
        return AgentResult(reply=restaurant.welcome_message, state={**state, "draft": draft})

    if not asks_delivery_fee and re.search(r"\b(men[uú]|carta|qu[eé] tienen|precios?)\b", text):
        return AgentResult(reply="Este es nuestro menú:\n" + menu_text(available, rates, descriptions=False),
                           state={**state, "draft": draft})

    if re.search(r"\b(horarios?|abierto|atienden|abren|cierran)\b", text):
        return AgentResult(reply=f"Nuestro horario es: {restaurant.opening_hours}",
                           state={**state, "draft": draft})

    # A requested date/time is preserved verbatim in the notes; there is no scheduling
    # field yet, so it must never be dropped from the accumulated draft.
    sched = re.search(r"((?:pasado\s+)?ma[ñn]ana|hoy)\s+a\s+las\s+\d+(?::\d+)?\s*(?:a\.?\s?m\.?|p\.?\s?m\.?|am|pm)?", text)
    if sched and sched.group(0) not in (draft.get("notes") or ""):
        draft["notes"] = ((draft.get("notes") or "") + " " + sched.group(0)).strip()

    if requested is None:
        requested = matched_items()

    # "Ese" / "esa" referring to several options Sabi just offered: ask which one, never
    # pick for the client, and keep the rest of the draft untouched. A single offered
    # option is what the client means.
    if not requested and re.search(r"\b(es[ae]s?|est[ae]s?)\b", text) and history:
        last_out = next((b for d, b in reversed(history) if d == "outbound"), "")
        candidates = [mi for mi in available if mi.name.lower() in last_out.lower()]
        if len(candidates) >= 2:
            options = " o ".join(f"{i.name} ({fmt_money(i.price, *rates)})" for i in candidates[:4])
            return AgentResult(
                reply=f"¿Cuál de estos: {options}? Lo demás de tu pedido queda igual.",
                state={**state, "draft": draft})
        if len(candidates) == 1:
            requested.append({"name": candidates[0].name, "quantity": 1, "extras": "", "notes": ""})

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
    if draft["order_type"] == "delivery" and zones:
        picked = delivery.find_zone(zones, text) or delivery.find_zone(zones, draft.get("address") or "")
        if picked:
            draft["delivery_zone"] = picked["name"]

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
        elif draft["order_type"] == "delivery" and zones and not draft.get("delivery_zone"):
            listing = ", ".join(f"{z['name']} +{fmt_money(z['fee'], *rates)}" for z in zones)
            missing.append(f"¿En qué zona estás? Delivery: {listing}.")
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
        quote = ""
        if (missing or upsell) and asks_delivery_fee and draft["order_type"] == "delivery":
            zone = delivery.find_zone(zones, draft.get("delivery_zone") or "")
            if zone:
                fee = fmt_money(zone["fee"], *rates) if zone["fee"] else "gratis"
                quote = f" Delivery ({zone['name']}) — {fee}."
        if missing:
            return AgentResult(reply=f"Anoté: {got}.{quote}{upsell} " + " ".join(missing),
                               state={**state, "draft": draft})
        if upsell:
            return AgentResult(reply=f"Anoté: {got}.{quote}{upsell} ¿O lo dejamos así?",
                               state={**state, "draft": draft})
        summary, _ = summarize_order(draft, {i.name.lower(): i for i in items}, rates_of(restaurant),
                                     delivery_fee_for(restaurant, draft))
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
