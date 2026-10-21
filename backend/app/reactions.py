"""Emoji reactions to inbound WhatsApp messages, chosen by the kind of message.

Deterministic keyword rules (no LLM call, no extra latency). Not every message gets a
reaction: when nothing matches, the agent just answers.
"""
import re
import unicodedata

_RULES: list[tuple[str, str]] = [
    # (regex over accent-stripped lowercase text, emoji) -- first match wins
    (r"\b(gracias|muchas gracias|te agradezco|mil gracias)\b", "🙏"),
    (r"\b(ya pague|pague|transferi|pago movil|comprobante)\b", "🙌"),
    (r"\b(queja|reclamo|problema|molesto|molesta|mal servicio|tarde|demor|no llego|equivoc)\w*", "😔"),
    (r"\b(entradas?|boletos?|tickets?|concierto|evento)s?\b", "🎟️"),
    (r"\b(quiero|quisiera|pedir|pedido|ordenar|comprar|dame|anota|anotame|llevo)\b", "🍽️"),
    (r"\b(hola|buenas|buenos dias|buenas tardes|buenas noches|saludos|epa|hey)\b", "👋"),
    (r"^(si|sii+|dale|listo|ok|okay|perfecto|de acuerdo|va|claro|correcto|confirmo)\W*$", "👍"),
    (r"(\?|\b(cuanto|cual|cuales|como|donde|que tienen|precio|horario|menu|abierto|abren)\b)", "👀"),
]
_COMPILED = [(re.compile(p), e) for p, e in _RULES]


def _plain(text: str) -> str:
    text = unicodedata.normalize("NFD", text.lower())
    return "".join(c for c in text if unicodedata.category(c) != "Mn").strip()


def reaction_for(text: str) -> str | None:
    plain = _plain(text or "")
    if not plain:
        return None
    for pattern, emoji in _COMPILED:
        if pattern.search(plain):
            return emoji
    return None
