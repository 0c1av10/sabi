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
    ("bqto", "Barquisimeto", "Lara"), ("Pto Ordaz", "Puerto Ordaz", "Bolívar"),
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


@pytest.mark.parametrize("text", ["pizza", "mi casa", "tres mensajes", "Acme", "Lechería del Este",
                                  "Centro de Lechería"])
def test_unknown_text_is_not_a_city(text):
    assert venezuela.find_city(text) is None
    assert venezuela.canonical(text) == text


def test_delivery_zone_written_another_way():
    zones = delivery.load_zones(NACIONAL_ZONES)
    assert delivery.find_zone(zones, "PLC")["name"] == "Puerto La Cruz"
    assert delivery.find_zone(zones, "Av. Principal de lecheria, edificio Mar Azul")["name"] == "Lechería"
    assert delivery.find_zone(zones, "Delivery a pto la cruz")["fee"] == 4.0
    assert delivery.find_zone(zones, "Caracas") is None
    assert delivery.find_zone(zones, "Delivery a PLC, no a BNA")["name"] == "Puerto La Cruz"


def test_partial_and_neighboring_zones_stay_their_own_area():
    zones = delivery.load_zones(json.dumps([{"name": "Centro de Lechería", "fee": 1.0},
                                            {"name": "Puerto Ordaz", "fee": 2.0}]))
    assert delivery.find_zone(zones, "Lechería, Av. Principal") is None
    assert delivery.find_zone(zones, "San Félix") is None
    assert delivery.find_zone(zones, "pto ordaz")["name"] == "Puerto Ordaz"
    assert delivery.find_zone(zones, "Ciudad Guayana, Pto Ordaz, Alta Vista")["name"] == "Puerto Ordaz"


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
        assert concierge.recommendation_city("Quiero comida en puerto la cruz") == "Puerto La Cruz"
        assert focus.declared_city("Estoy en Puerto La Cruz") == "Puerto La Cruz"
        assert focus.declared_city("Estoy en la casa") == ""


# The example order line Sabi suggests after listing local options must reach the business.
async def test_suggested_order_line_routes_to_business(Session, sent):
    async with Session() as db:
        await _catalog(db)
        reply = await focus.city_reply(db, "111", "Estoy en Lechería")
        assert "«quiero pedir en NACIONAL Restaurante»" in reply
        assert await webhook._events_route(db, "111", "quiero pedir en NACIONAL Restaurante") is None
        restaurant, _, text = await webhook._resolve(db, "111", "quiero pedir en NACIONAL Restaurante")
        assert restaurant and restaurant.slug == "nacional" and text is None
        assert (await focus.get(db, "111")).city == "Lechería"


async def test_city_written_in_the_order_is_kept(Session, sent):
    async with Session() as db:
        await _catalog(db)
        await focus.city_reply(db, "111", "Estoy en Lechería")
        restaurant, _, _ = await webhook._resolve(db, "111", "quiero pedir en NACIONAL Restaurante en plc")
        assert restaurant and (await focus.get(db, "111")).city == "Puerto La Cruz"


@pytest.mark.parametrize("question", ["¿En qué ciudad queda?", "en que ciudad queda",
                                      "NACIONAL Restaurante en qué ciudad queda?", "¿Dónde queda NACIONAL Restaurante?"])
async def test_where_is_question_is_not_a_city(Session, sent, question):
    async with Session() as db:
        await _catalog(db)
        await focus.save(db, "111", domain="restaurant", entity="NACIONAL Restaurante", city="Lechería")
        assert focus.declared_city(question) == ""
        reply = await webhook._events_route(db, "111", question)
        assert reply == ("NACIONAL Restaurante hace delivery en Lechería, Barcelona y Puerto La Cruz, "
                         "según las zonas que registró. No tengo su dirección exacta verificada.")
        assert (await focus.get(db, "111")).city == "Lechería"


async def test_where_is_question_without_registered_zones(Session, sent):
    async with Session() as db:
        await _catalog(db)
        reply = await webhook._events_route(db, "111", "¿Dónde queda MC Racuchos?")
        assert reply == "No tengo registrada la ciudad de MC Racuchos y no voy a adivinarla."


@pytest.mark.parametrize("question", ["¿Dónde queda Pizzería Roma?", "¿Dónde queda el gym?",
                                      "¿En qué ciudad queda? https://nacional.example/sedes"])
async def test_where_is_question_about_something_else_is_left_to_other_routes(Session, question):
    async with Session() as db:
        await _catalog(db)
        await focus.save(db, "111", domain="restaurant", entity="NACIONAL Restaurante", city="Lechería")
        assert await focus.location_reply(db, "111", question) is None
        assert await focus.location_reply(db, "222", "¿En qué ciudad queda?") is None


def test_where_is_question_keeps_the_named_place():
    from app.auth import named_business_query
    assert named_business_query("¿Dónde queda Pizzería Roma?") == ("Roma", "")
    assert named_business_query("Pizzería Roma en qué ciudad queda?") == ("Roma", "")


async def test_question_saved_as_city_is_dropped(Session, sent):
    async with Session() as db:
        await _catalog(db)
        await focus.save(db, "111", domain="place", entity="NACIONAL Restaurante", city="qué ciudad queda")
        assert await focus.get(db, "111") is None
        _, _, text = await webhook._resolve(db, "111", "Como me llamo")
        assert "qué ciudad queda" not in (text or "")


async def test_location_follow_up_keeps_unresolved_place(Session, sent):
    async with Session() as db:
        await focus.save(db, "111", domain="place", entity="Pizzería Roma")
        assert await focus.pending_city_answer(db, "111", "¿Dónde queda exactamente?") == ""
        assert venezuela.location_subject("¿Dónde queda exactamente?") == ""
        await webhook._events_route(db, "111", "¿Dónde queda exactamente?")
        assert (await focus.get(db, "111")).entity == "Pizzería Roma"


def test_name_request_with_an_order_is_left_to_the_order():
    from app import memory
    assert memory.name_reply(None, "Llámame por mi nombre y quiero pedir en NACIONAL Restaurante") == ""
    assert memory.name_reply(None, "Hola Sabi, ¿cómo me llamo?") == "Aún no sé tu nombre. ¿Cómo te llamas? Así te hablo por tu nombre."


def test_name_question_variants_are_answered():
    from app import memory
    contact = memory.Contact(phone="111", name="Octavio")
    assert memory.name_reply(contact, "¿Sabes cuál es mi nombre?") == "Te llamas Octavio. ¿En qué te ayudo?"
    assert memory.name_reply(contact, "¿Recuerdas cómo me llamo?") == "Te llamas Octavio. ¿En qué te ayudo?"




ASK = "¿Cómo te llamas? Así te hablo por tu nombre."


@pytest.mark.parametrize("reply", ["Boxeo", "Reservar cupo", "¿Quedan cupos?", "Quedan cupos", "Cupo", "cine",
                                   "Lechería", "comida", "Mañana", "NACIONAL Restaurante", "Hola", "Ok"])
async def test_reply_to_name_prompt_that_is_not_a_name(Session, sent, reply):
    from app import memory
    async with Session() as db:
        await memory.note(db, "111", topic="cine")
        assert await webhook._events_route(db, "111", "Como me llamo") == "Aún no sé tu nombre. " + ASK
        await webhook._events_route(db, "111", reply)
        contact = await memory.get(db, "111")
        assert not contact.name and not memory.name_pending(contact)


@pytest.mark.parametrize("reply,name", [("Octavio", "Octavio"), ("ana maría", "Ana María"),
                                        ("Ana Cupo", "Ana Cupo"), ("Ana Rondón", "Ana Rondón"),
                                        ("Me llamo Yulimar", "Yulimar"), ("Soy Deivis", "Deivis")])
async def test_reply_to_name_prompt_that_is_a_name(Session, sent, reply, name):
    from app import memory
    async with Session() as db:
        await memory.note(db, "111", topic="cine")
        await webhook._events_route(db, "111", "Como me llamo")
        first = name.split()[0]
        assert await webhook._events_route(db, "111", reply) == \
            f"¡Mucho gusto, {first}! Ya me quedo con tu nombre. ¿En qué te ayudo?"
        contact = await memory.get(db, "111")
        assert contact.name == name and contact.last_topic == "cine"
        assert await webhook._events_route(db, "111", "¿Cómo me llamo?") == f"Te llamas {first}. ¿En qué te ayudo?"
        assert await webhook._events_route(db, "111", "Adresame con mi nombre") == f"Claro, {first}. ¿En qué te ayudo?"


async def test_greeting_asks_for_unknown_name_then_uses_it(Session, sent):
    async with Session() as db:
        text, _ = await concierge.reply(db, "Hola", "333")
        assert text == "¡Hola! 👋 Soy Sabi. " + ASK
        await webhook._events_route(db, "333", "Ana María")
        text, _ = await concierge.reply(db, "Hola", "333")
        assert text.startswith("Hola de nuevo, Ana.")


async def test_gym_signup_keeps_its_own_name_step(Session, sent):
    from app import gym_whatsapp
    async with Session() as db:
        await gym_whatsapp.reply_for(db, "222", "Quiero una clase de boxeo")
        await webhook._events_route(db, "222", "Ana")
        assert (await gym_whatsapp._state(db, "222"))[1].get("step") != "name"
