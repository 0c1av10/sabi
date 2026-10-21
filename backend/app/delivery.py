"""Delivery pricing by zone (USD, like menu prices).

A restaurant stores `delivery_zones` as JSON text: [{"name": "Lechería", "fee": 2.0}, ...].
With zones, a delivery order must pick one and pays that zone's fee. Without zones the flat
`delivery_fee` applies (None = unknown, the local confirms).
"""
import json
import re
import unicodedata
from typing import Optional

MAX_ZONES = 20


def plain(text: str) -> str:
    text = unicodedata.normalize("NFD", (text or "").lower())
    return re.sub(r"\s+", " ", "".join(c for c in text if unicodedata.category(c) != "Mn")).strip()


def clean_zones(zones) -> list[dict]:
    """Validate/normalize a list of {name, fee}. Invalid rows are dropped; duplicates keep the first."""
    out, seen = [], set()
    for z in zones or []:
        if not isinstance(z, dict):
            continue
        name = re.sub(r"\s+", " ", str(z.get("name") or "")).strip()[:60]
        try:
            fee = round(float(z.get("fee")), 2)
        except (TypeError, ValueError):
            continue
        if not name or not (0 <= fee <= 99) or plain(name) in seen:
            continue
        seen.add(plain(name))
        out.append({"name": name, "fee": fee})
        if len(out) >= MAX_ZONES:
            break
    return out


def load_zones(raw: Optional[str]) -> list[dict]:
    try:
        return clean_zones(json.loads(raw)) if raw else []
    except ValueError:
        return []


def dump_zones(zones) -> str:
    return json.dumps(clean_zones(zones), ensure_ascii=False)


def zones_of(restaurant) -> list[dict]:
    return load_zones(getattr(restaurant, "delivery_zones", ""))


def find_zone(zones: list[dict], text: str) -> Optional[dict]:
    """Zone named exactly, or mentioned inside `text` (accent/case-insensitive); longest name wins."""
    needle = plain(text)
    if not needle:
        return None
    for z in zones:
        if plain(z["name"]) == needle:
            return z
    hits = [z for z in zones if re.search(rf"(?<!\w){re.escape(plain(z['name']))}(?!\w)", needle)]
    return max(hits, key=lambda z: len(z["name"])) if hits else None


def fee_for(restaurant, order_type: Optional[str], zone_name: str = "") -> float:
    """Delivery fee to add to an order. 0 for pickup, for an unknown fee, or while no zone is chosen."""
    if order_type != "delivery":
        return 0.0
    zones = zones_of(restaurant)
    if zones:
        z = find_zone(zones, zone_name)
        return z["fee"] if z else 0.0
    return restaurant.delivery_fee or 0.0


def describe(restaurant, fmt) -> str:
    """Text for the agent's context. `fmt(usd)` renders a price."""
    zones = zones_of(restaurant)
    if zones:
        listing = "; ".join(f"{z['name']}: " + ("gratis" if z["fee"] == 0 else fmt(z["fee"])) for z in zones)
        head = (f"Delivery por zona ({listing}). Si el pedido es delivery, pregunta la zona, usa solo estas "
                "zonas (delivery_zone con el nombre exacto) y el costo se suma al total. Si está fuera de estas zonas, "
                "dilo y ofrece pasar con el dueño.")
    elif restaurant.delivery_fee is None:
        head = "Costo de delivery: no definido; di que el local lo confirma al aprobar el pedido, no inventes un monto."
    elif restaurant.delivery_fee == 0:
        head = "Costo de delivery: gratis."
    else:
        head = f"Costo de delivery: {fmt(restaurant.delivery_fee)} (se suma al total solo si es delivery)."
    info = getattr(restaurant, "delivery_info", "") or ""
    return head + (f"\nCondiciones de delivery del local: {info}" if info else "")


# ---- reading zones from a restaurant's site ------------------------------------------

_ZONE_TEXT = re.compile(
    r"([A-ZÁÉÍÓÚÑ][A-Za-zÁÉÍÓÚÑáéíóúñ .]{2,40}?)\s*[·|:\-–—]?\s*\+\s?\$\s?(\d{1,2}(?:[.,]\d{1,2})?)\b")
_ZONE_OBJ = re.compile(
    r"[\"']?(?:name|nombre|zone|zona)[\"']?\s*:\s*[\"'`]([^\"'`\\]{2,40})[\"'`]"
    r"[^{}]{0,120}?[\"']?(?:fee|cost|costo|price|precio|tarifa)[\"']?\s*:\s*[\"'`]?\$?\s?(\d{1,2}(?:[.,]\d{1,2})?)", re.I)


def extract_zones(texts: list[str], visible_lines) -> list[dict]:
    """Zones with a fee from page text ("Lechería · +$2.00") or JS objects ({zona:"Lechería", costo:2}).
    Needs at least two distinct zones, so a stray "+$2" line is never taken as a zone list."""
    found: list[dict] = []
    for doc in texts:
        for m in _ZONE_OBJ.finditer(doc):
            found.append({"name": m.group(1), "fee": m.group(2).replace(",", ".")})
        for line in visible_lines(doc):
            for m in _ZONE_TEXT.finditer(line):
                found.append({"name": m.group(1).strip(" ·|:-–—"), "fee": m.group(2).replace(",", ".")})
    zones = clean_zones(found)
    return zones if len(zones) >= 2 else []
