"""Venezuelan city knowledge base, checked against messages from real WhatsApp conversations."""
import json

import pytest

from app import concierge, conversation_focus as focus, delivery, memory, venezuela
from app.models import Restaurant
from app.routers import webhook

NACIONAL_ZONES = json.dumps([{"name": "Lechería", "fee": 2.0}, {"name": "Barcelona", "fee": 3.0},
                             {"name": "Puerto La Cruz", "fee": 4.0}], ensure_ascii=False)


async def _catalog(db):
    db.add(Restaurant(name="NACIONAL Restaurante", slug="nacional", pin="0000",
                      tagline="Pollo asado y cachapas en Lechería", delivery_zones=NACIONAL_ZONES))
    # Tagline says Lechería but no delivery zone is registered: not verified coverage.
    db.add(Restaurant(name="MC Racuchos", slug="mc-racuchos", pin="0000",
                      tagline="Pastelitos, arepas y tequeños en Lechería"))
    db.add(Restaurant(name="Prueba Interna", slug="prueba", pin="0000", delivery_zones=NACIONAL_ZONES))
    await db.commit()


@pytest.fixture
def sent(monkeypatch):
    out = []

    async def send(phone, text):
        out.append(text)
        return {"mock": True}
    monkeypatch.setattr(webhook, "send_whatsapp_message", send)
    return out


@pytest.mark.parametrize("written,name,state", [
    ("lecheria", "Lechería", "Anzoátegui"), ("Lechería", "Lechería", "Anzoátegui"),
    ("PLC", "Puerto La Cruz", "Anzoátegui"), ("pto la cruz", "Puerto La Cruz", "Anzoátegui"),
    ("ccs", "Caracas", "Distrito Capital"), ("Caracas, Venezuela", "Caracas", "Distrito Capital"),
    ("bqto", "Barquisimeto", "Lara"), ("Puerto Ordaz", "Ciudad Guayana", "Bolívar"),
    ("maturin", "Maturín", "Monagas"), ("la ciudad de Mérida", "Mérida", "Mérida"),
    ("margarita", "Isla de Margarita", "Nueva Esparta"), ("MCBO", "Maracaibo", "Zulia"),
])
def test_city_aliases(written, name, state):
    city = venezuela.find_city(written)
    assert city and (city.name, city.state) == (name, state)


def test_every_state_has_its_capital():
    states = {c.state for c in venezuela.CITIES}
    assert len(states) == 24  # 23 states + Distrito Capital
    for capital in ("Caracas", "Barcelona", "Valencia", "Maracaibo", "Barquisimeto", "Cumaná",
                    "San Cristóbal", "Puerto Ayacucho", "Tucupita", "La Asunción", "San Felipe"):
        assert venezuela.find_city(capital)


@pytest.mark.parametrize("text", ["pizza", "mi casa", "tres mensajes", "Acme", "Lechería del Este"])
def test_unknown_text_is_not_a_city(text):
    assert venezuela.find_city(text) is None
    assert venezuela.canonical(text) == text


def test_delivery_zone_written_another_way():
    zones = delivery.load_zones(NACIONAL_ZONES)
    assert delivery.find_zone(zones, "PLC")["name"] == "Puerto La Cruz"
    assert delivery.find_zone(zones, "Av. Principal de lecheria, edificio Mar Azul")["name"] == "Lechería"
    assert delivery.find_zone(zones, "Delivery a pto la cruz")["fee"] == 4.0
    assert delivery.find_zone(zones, "Caracas") is None


# Real conversation (2026-11-20): "En lechería que me recomiendas" → "comida".
async def test_food_in_covered_city_lists_only_registered_zones(Session, sent):
    async with Session() as db:
        await _catalog(db)
        assert await webhook._events_route(db, "111", "En lechería que me recomiendas") == \
            "¿Buscas comida o un plan de cine en Lechería?"
        reply = await webhook._events_route(db, "111", "comida")
        assert "NACIONAL Restaurante" in reply and "delivery a Lechería ($2,00)" in reply
        assert "MC Racuchos" not in reply and "Prueba" not in reply
        assert (await memory.get(db, "111")).last_topic == "recomendación de locales: NACIONAL Restaurante"


async def test_alias_city_in_direct_food_request(Session, sent):
    async with Session() as db:
        await _catalog(db)
        reply = await webhook._events_route(db, "111", "Quiero comida en PLC")
        assert "En Puerto La Cruz" in reply and "($4,00)" in reply
        text = await concierge.recommendations(db, body="Quiero comida en lecheria", phone="111")
        assert "NACIONAL Restaurante" in text and "MC Racuchos" not in text


async def test_uncovered_city_still_refuses_to_invent(Session, sent):
    async with Session() as db:
        await _catalog(db)
        reply = await webhook._events_route(db, "111", "Quiero comida en Valencia")
        assert "filtro geográfico" in reply and "NACIONAL" not in reply
        text = await concierge.recommendations(db, body="Quiero comida en Caracas")
        assert "filtro geográfico" in text and "NACIONAL" not in text


# Real conversation: after the city, the customer names the business ("Y nacional ?").
async def test_named_business_after_city_routes_and_keeps_city(Session, sent):
    async with Session() as db:
        await _catalog(db)
        reply = await focus.city_reply(db, "111", "Estoy en Lechería")
        assert "NACIONAL Restaurante" in reply
        restaurant, _, text = await webhook._resolve(db, "111", "Y nacional ?")
        assert restaurant and restaurant.slug == "nacional" and text is None
        active = await focus.get(db, "111")
        assert (active.domain, active.entity, active.city) == ("restaurant", "NACIONAL Restaurante", "Lechería")


async def test_city_without_coverage_is_not_given_to_business(Session, sent):
    async with Session() as db:
        await _catalog(db)
        reply = await focus.city_reply(db, "111", "Estoy en Valencia")
        assert "fuente verificada" in reply and "NACIONAL" not in reply
        restaurant, _, _ = await webhook._resolve(db, "111", "Y nacional ?")
        # NACIONAL does not deliver to Valencia, so the order does not inherit that city.
        assert restaurant and (await focus.get(db, "111")).city == ""


# Real conversation: "Nacional" → "Restaurante" → bare "Lecheria" (no accent).
async def test_bare_city_answer_is_canonical(Session, sent):
    async with Session() as db:
        await focus.save(db, "111", domain="place", entity="Pizzería Roma")
        await focus.city_reply(db, "111", "Lecheria")
        assert (await focus.get(db, "111")).city == "Lechería"
        assert focus.declared_city("Estoy en plc") == "Puerto La Cruz"
        assert concierge.recommendation_city("En ccs que me recomiendas") == "Caracas"
        assert concierge.recommendation_city("En Valencia que me recomiendas") == "Valencia"


# The example order line Sabi suggests after listing local options must reach the business.
async def test_suggested_order_line_routes_to_business(Session, sent):
    async with Session() as db:
        await _catalog(db)
        reply = await focus.city_reply(db, "111", "Estoy en Lechería")
        assert "«quiero pedir en NACIONAL Restaurante»" in reply
        restaurant, _, text = await webhook._resolve(db, "111", "quiero pedir en NACIONAL Restaurante")
        assert restaurant and restaurant.slug == "nacional" and text is None
        assert (await focus.get(db, "111")).city == "Lechería"
