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
        assert "• *NACIONAL Restaurante*\n" in reply and "$" not in reply
        assert "MC Racuchos" not in reply and "Prueba" not in reply
        assert (await memory.get(db, "111")).last_topic == "recomendación de locales: NACIONAL Restaurante"


async def test_alias_city_in_direct_food_request(Session, sent):
    async with Session() as db:
        await _catalog(db)
        reply = await webhook._events_route(db, "111", "Quiero comida en PLC")
        assert "En Puerto La Cruz" in reply and "NACIONAL Restaurante" in reply and "$" not in reply
        text = await concierge.recommendations(db, body="Quiero comida en lecheria", phone="111")
        assert "NACIONAL Restaurante" in text and "MC Racuchos" not in text


async def test_uncovered_city_still_refuses_to_invent(Session, sent):
    async with Session() as db:
        await _catalog(db)
        reply = await webhook._events_route(db, "111", "Quiero comida en Valencia")
        assert reply.startswith("En Valencia no tengo locales verificados.") and "NACIONAL" not in reply
        text = await concierge.recommendations(db, body="Quiero comida en Caracas")
        assert "no tengo locales verificados" in text and "NACIONAL" not in text


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
        # No confirmed coverage: NACIONAL registers zones for other cities and stays out; the
        # zone-less MC Racuchos is listed with coverage to confirm, never promised (docs/CITY_LISTING.md).
        assert "te puedo atender" not in reply and "NACIONAL" not in reply
        assert "MC Racuchos" in reply and "sin delivery a Valencia confirmado" in reply
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
        assert reply == ("NACIONAL Restaurante hace delivery a Lechería, Barcelona y "
                         "Puerto La Cruz. No tengo su dirección exacta.")
        assert (await focus.get(db, "111")).city == "Lechería"


async def test_where_is_question_without_registered_zones(Session, sent):
    async with Session() as db:
        await _catalog(db)
        reply = await webhook._events_route(db, "111", "¿Dónde queda MC Racuchos?")
        assert reply == "No tengo la ubicación de MC Racuchos."


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


@pytest.mark.parametrize("reply", ["Juan Griego", "San Juan de los Morros"])
def test_city_starting_with_a_first_name_is_not_a_name(reply):
    from app import memory
    assert memory.bare_name(reply) == ""
    assert memory.bare_name("Juan Pérez") == "Juan Pérez"


async def test_introduction_with_a_question_still_gets_its_answer(Session, sent):
    from app import memory
    async with Session() as db:
        await memory.ask_name(db, "111")
        reply = await webhook._events_route(db, "111", "Soy Ana, ¿hay boxeo?")
        assert not (reply or "").startswith("¡Mucho gusto")
        contact = await memory.get(db, "111")
        assert contact.name == "Ana" and not memory.name_pending(contact)


@pytest.mark.parametrize("reply", ["Margarita Pérez", "Ana Valencia", "Carlos Maturín", "Ana Pérez-García"])
def test_name_containing_a_city_word_is_still_a_name(reply):
    from app import memory
    assert memory.bare_name(reply).replace(" ", "") == reply.replace(" ", "").replace("-", "")


@pytest.mark.parametrize("reply", ["Margarita, hay cine", "Ana y quiero pizza", "Carlos: boxeo", "Margarita, 2",
                                   "Ana 2", "Octavio?"])
def test_bare_name_must_be_the_whole_reply(reply):
    from app import memory
    assert memory.bare_name(reply) == ""


async def test_city_options_show_the_fee_only_when_asked(Session, sent):
    async with Session() as db:
        await _catalog(db)
        reply = await venezuela.local_options(db, "Lechería")
        assert reply.startswith("En Lechería te puedo atender con estos locales:\n• *NACIONAL Restaurante*\n")
        assert "$" not in reply
        # Zone-less businesses appear with coverage to confirm: no fee, no promise.
        assert "MC Racuchos" in reply and "sin delivery a Lechería confirmado" in reply
        assert "registr" not in reply and "zonas" not in reply
        reply = await focus.fee_reply(db, "222", "¿Cuánto sale el delivery a Lechería?")
        assert "• *NACIONAL Restaurante* — delivery a Lechería ($2,00)" in reply
        assert "registr" not in reply and "zonas" not in reply




async def test_product_from_another_business_is_not_a_silent_switch(Session, sent):
    from app.models import MenuItem
    async with Session() as db:
        await _catalog(db)
        db.add(Restaurant(name="Bizza", slug="bizza", pin="0000"))
        await db.flush()
        bizza = (await db.execute(Restaurant.__table__.select().where(Restaurant.slug == "bizza"))).first()
        db.add(MenuItem(restaurant_id=bizza.id, name="REFRESCO 1L.", price=2.5, category="Bebidas"))
        await db.commit()
        restaurant, _, text = await webhook._resolve(db, "111", "Tiene refresco")
        assert restaurant and restaurant.slug == "bizza"
        await memory.set_topic(db, "222", "tu pedido en NACIONAL Restaurante")
        restaurant, _, text = await webhook._resolve(db, "222", "Tiene refresco")
        assert restaurant is None and text == ("Eso lo encontré en *Bizza*. "
                                               "¿Quieres pedirlo allí o seguimos con NACIONAL Restaurante?")
        restaurant, _, _ = await webhook._resolve(db, "222", "Sí, quiero un refresco")
        assert restaurant and restaurant.slug == "bizza"
        await memory.set_topic(db, "333", "tu pedido en NACIONAL Restaurante")
        await webhook._resolve(db, "333", "Tiene refresco")
        restaurant, routed, _ = await webhook._resolve(db, "333", "Sí")
        assert restaurant and restaurant.slug == "bizza" and routed == "Tiene refresco"
        await memory.set_topic(db, "555", "tu pedido en NACIONAL Restaurante")
        await webhook._resolve(db, "555", "Tiene refresco")
        restaurant, routed, _ = await webhook._resolve(db, "555", "No, seguimos. Quiero un refresco")
        assert restaurant and restaurant.slug == "nacional"
        assert (await memory.get(db, "555")).last_topic == "tu pedido en NACIONAL Restaurante"
        restaurant, _, _ = await webhook._resolve(db, "444", "Quiero un refresco de Bizza")
        assert restaurant and restaurant.slug == "bizza"


async def test_business_name_with_parenthesis_is_not_a_switch(Session, sent):
    from app.models import MenuItem
    async with Session() as db:
        db.add(Restaurant(name="Arepera (Lechería)", slug="arepera", pin="0000"))
        await db.flush()
        rid = (await db.execute(Restaurant.__table__.select().where(Restaurant.slug == "arepera"))).first().id
        db.add(MenuItem(restaurant_id=rid, name="REFRESCO 1L.", price=2.5, category="Bebidas"))
        await db.commit()
        await memory.set_topic(db, "111", "tu pedido en Arepera (Lechería) (recomendación de locales: Lechería)")
        restaurant, _, text = await webhook._resolve(db, "111", "Tiene refresco")
        assert restaurant and restaurant.slug == "arepera" and text is None


async def test_greeting_asks_when_the_saved_name_is_not_usable(Session, sent):
    async with Session() as db:
        db.add(memory.Contact(phone="111", name="Entonces", name_source="profile", last_topic="tu pedido en NACIONAL Restaurante"))
        await db.commit()
        text, _ = await concierge.reply(db, "Hola", "111")
        assert text == "Hola de nuevo. " + memory.ASK_NAME


async def test_long_request_is_never_forwarded_cut(Session, sent):
    from app.models import MenuItem
    async with Session() as db:
        await _catalog(db)
        db.add(Restaurant(name="Bizza", slug="bizza", pin="0000"))
        await db.flush()
        bizza = (await db.execute(Restaurant.__table__.select().where(Restaurant.slug == "bizza"))).first()
        db.add(MenuItem(restaurant_id=bizza.id, name="REFRESCO 1L.", price=2.5, category="Bebidas"))
        await db.commit()
        await memory.set_topic(db, "222", "tu pedido en NACIONAL Restaurante")
        long = "Tiene refresco de 1 litro bien frío para retirar mañana a las 7 de la noche en la sede de Lechería"
        await webhook._resolve(db, "222", long)
        restaurant, routed, _ = await webhook._resolve(db, "222", "Sí")
        assert restaurant.slug == "bizza" and routed == "Sí"


async def test_reply_naming_a_business_overrides_the_switch_offer(Session, sent):
    from app.models import MenuItem
    async with Session() as db:
        await _catalog(db)
        db.add(Restaurant(name="Bizza", slug="bizza", pin="0000"))
        await db.flush()
        bizza = (await db.execute(Restaurant.__table__.select().where(Restaurant.slug == "bizza"))).first()
        db.add(MenuItem(restaurant_id=bizza.id, name="REFRESCO 1L.", price=2.5, category="Bebidas"))
        await db.commit()
        await memory.set_topic(db, "222", "tu pedido en NACIONAL Restaurante")
        await webhook._resolve(db, "222", "Tiene refresco")
        restaurant, _, text = await webhook._resolve(db, "222", "En NACIONAL Restaurante")
        assert restaurant and restaurant.slug == "nacional" and text is None
        await memory.set_topic(db, "555", "tu pedido en NACIONAL Restaurante")
        await webhook._resolve(db, "555", "Tiene refresco")
        await memory.set_topic(db, "999", "tu pedido en NACIONAL Restaurante")
        await webhook._resolve(db, "999", "Tiene refresco")
        restaurant, _, _ = await webhook._resolve(db, "999", "Sí, en Bizza [sabi:nacional]")
        assert restaurant and restaurant.slug == "nacional"
        restaurant, routed, _ = await webhook._resolve(db, "555", "Bizza, quiero una pizza sin cebolla")
        assert restaurant and restaurant.slug == "bizza" and routed.endswith("sin cebolla")
        for phone, reply in [("333", "Sí, nada de NACIONAL"), ("444", "En Bizza no"), ("888", "No quiero NACIONAL"),
                             ("1010", "Bizza, mejor no"), ("1111", "Bizza o NACIONAL?"),
                             ("666", "No, gracias. Y nada de NACIONAL"), ("777", "Sí, sin problema con Bizza")]:
            await memory.set_topic(db, phone, "tu pedido en NACIONAL Restaurante")
            await webhook._resolve(db, phone, "Tiene refresco")
            restaurant, _, text = await webhook._resolve(db, phone, reply)
            assert restaurant is None and text.startswith("¿Lo pedimos en *Bizza*"), reply
            restaurant, _, _ = await webhook._resolve(db, phone, "Bizza")
            assert restaurant and restaurant.slug == "bizza", reply


async def test_owner_chat_city_question_and_fee_after_city_list(Session, sent):
    async with Session() as db:
        await _catalog(db)
        await focus.save(db, "111", domain="general", entity="pending_recommendation_domain", city="Lechería")
        assert "NACIONAL Restaurante" in await venezuela.local_options(db, "Lechería", "111")
        assert focus.declared_city("En qué ciudad es esto") == ""
        reply = await webhook._events_route(db, "111", "En qué ciudad es esto")
        assert reply.startswith("NACIONAL Restaurante hace delivery") and "Barcelona" in reply
        reply = await webhook._events_route(db, "111", "Y cuánto sale a Barcelona ?")
        assert "El delivery de NACIONAL Restaurante a Barcelona cuesta $3,00." in reply
        # The zone-less listed business never gets an invented fee: the local confirms.
        assert "MC Racuchos a Barcelona lo confirma el local" in reply
        reply = await webhook._events_route(db, "111", "¿Cuánto cuesta el delivery a Caracas?")
        assert "NACIONAL Restaurante no hace delivery a Caracas." in reply
        assert "MC Racuchos a Caracas lo confirma el local" in reply


async def test_question_saved_as_city_is_ignored(Session, sent):
    async with Session() as db:
        await focus.save(db, "111", domain="place", entity="", city="qué ciudad es esto")
        assert await focus.get(db, "111") is None


@pytest.mark.asyncio
async def test_product_price_question_is_not_a_delivery_fee(Session, sent):
    async with Session() as db:
        await _catalog(db)
        await focus.save(db, "111", domain="restaurant", entity="NACIONAL Restaurante")
        assert await focus.fee_reply(db, "111", "¿Cuánto cuesta una pizza en Barcelona?") is None
        assert await focus.fee_reply(db, "111", "¿Cuánto cuesta el delivery a Barcelona?") == (
            "El delivery de NACIONAL Restaurante a Barcelona cuesta $3,00."
        )


@pytest.mark.asyncio
async def test_fee_without_zones_uses_flat_fee_not_a_refusal(Session, sent):
    async with Session() as db:
        await _catalog(db)
        db.add(Restaurant(name="Arepera Plana", slug="plana", pin="0000", delivery_fee=1.5))
        await db.commit()
        await focus.save(db, "111", domain="restaurant", entity="Arepera Plana")
        reply = await focus.fee_reply(db, "111", "¿Cuánto cuesta el delivery a Barcelona?")
        assert reply == "El delivery de Arepera Plana cuesta $1,50; el local confirma si llega a Barcelona."
        await focus.save(db, "111", domain="restaurant", entity="MC Racuchos")
        reply = await focus.fee_reply(db, "111", "¿Cuánto cuesta el delivery a Barcelona?")
        assert "no hace delivery" not in reply and "lo confirma el local" in reply


@pytest.mark.asyncio
async def test_unresolved_place_fee_question_ignores_older_list(Session, sent):
    async with Session() as db:
        await _catalog(db)
        await focus.save(db, "111", domain="general", entity="pending_recommendation_domain", city="Lechería")
        await venezuela.local_options(db, "Lechería", "111")
        await focus.save(db, "111", domain="place", entity="Pizzería Roma", city="")
        assert await focus.fee_reply(db, "111", "¿Cuánto sale el delivery a Barcelona?") is None


@pytest.mark.asyncio
async def test_fee_question_naming_the_business(Session, sent):
    async with Session() as db:
        await _catalog(db)
        assert await focus.fee_reply(db, "111", "¿Cuánto sale el delivery de NACIONAL a Barcelona?") == (
            "El delivery de NACIONAL Restaurante a Barcelona cuesta $3,00."
        )
        assert await focus.fee_reply(db, "111", "¿Cuánto cuesta una pizza de NACIONAL en Barcelona?") is None


@pytest.mark.asyncio
async def test_fee_question_unknown_business_and_origin_city(Session, sent):
    async with Session() as db:
        await _catalog(db)
        await focus.save(db, "111", domain="restaurant", entity="NACIONAL Restaurante")
        assert await focus.fee_reply(db, "111", "¿Cuánto sale el delivery de Pizzería Roma a Barcelona?") is None
        assert await focus.fee_reply(db, "111", "¿Cuánto sale el delivery de NACIONAL en Lechería a Barcelona?") == (
            "El delivery de NACIONAL Restaurante a Barcelona cuesta $3,00."
        )
        assert await focus.fee_reply(db, "111", "¿Cuánto sale el delivery a Barcelona en la noche?") == (
            "El delivery de NACIONAL Restaurante a Barcelona cuesta $3,00."
        )


@pytest.mark.asyncio
async def test_fee_question_origin_city_is_not_destination_or_business(Session, sent):
    async with Session() as db:
        await _catalog(db)
        await focus.save(db, "111", domain="restaurant", entity="NACIONAL Restaurante")
        expected = "El delivery de NACIONAL Restaurante a Barcelona cuesta $3,00."
        assert await focus.fee_reply(db, "111", "¿Cuánto sale a Barcelona si el local está en Lechería?") == expected
        assert await focus.fee_reply(db, "111", "¿Cuánto sale el delivery de Lechería a Barcelona?") == expected
        assert await focus.fee_reply(db, "111", "¿Cuánto cuesta el delivery en Lechería?") == (
            "El delivery de NACIONAL Restaurante a Lechería cuesta $2,00."
        )


async def test_owner_sequence_keeps_the_city_through_food_and_cinema(Session, sent, monkeypatch):
    from app import cinema_whatsapp as cinema
    queries = []

    async def run(body, **kw):
        queries.append(body)
        return cinema.UNAVAILABLE

    async def quiet(*args):
        return {"mock": True}
    monkeypatch.setattr(cinema, "run_cinema_agent", run)
    monkeypatch.setattr(cinema, "send_whatsapp_message", quiet)
    monkeypatch.setattr(cinema.settings, "cinema_mcp_enabled", True)

    async def say(db, text):
        reply = await webhook._events_route(db, "111", text)
        if reply is None:
            restaurant, _, reply = await webhook._resolve(db, "111", text)
            assert restaurant is None, f"{text!r} went to {restaurant.name}"
        return reply

    async with Session() as db:
        await _catalog(db)
        step1 = await say(db, "Estoy buscando dónde comer en Cumaná. Solo quiero información, no hagas pedidos ni reservas.")
        assert step1.startswith("En Cumaná no tengo locales verificados.")
        assert "NACIONAL" not in step1
        step2 = await say(db, "¿Y pizza?")
        assert step2.startswith("En Cumaná no tengo locales de pizza verificados.")
        step3 = await say(db, "Mejor en Lechería.")
        assert step3.startswith("En Lechería no tengo locales de pizza verificados.")
        assert "*NACIONAL Restaurante*" in step3 and "$" not in step3
        step4 = await say(db, "Ahora quiero ver qué hay en el cine allí. Solo consulta, no compres entradas.")
        assert step4 == "No logré verificar la cartelera de cine en Lechería. No tengo horarios confirmados para mostrarte."
        assert "Ciudad explícita para esta consulta: Lechería." in queries[0]


@pytest.mark.parametrize("text,rejects", [
    ("No quiero comida, mejor cine", True), ("ni cine ni nada", True), ("cine no", True),
    ("Solo quiero información, no hagas pedidos ni reservas de comida", False),
    ("Quiero ir al cine, no compres entradas", False),
])
def test_no_about_something_else_is_not_turning_a_topic_down(text, rejects):
    assert concierge.rejects_domain(text) is rejects


async def _lecheria_food(db):
    await _catalog(db)
    reply = await webhook._events_route(db, "111", "Estoy buscando dónde comer en Lechería.")
    assert reply.startswith("En Lechería te puedo atender")


async def test_a_named_business_after_a_food_search_goes_to_that_business(Session, sent):
    async with Session() as db:
        await _lecheria_food(db)
        reply = await webhook._events_route(db, "111", "Quiero una pizza de NACIONAL")
        assert not (reply or "").startswith("En Lechería")


async def test_an_unknown_city_after_a_food_search_is_not_the_old_city(Session, sent):
    async with Session() as db:
        await _lecheria_food(db)
        reply = await webhook._events_route(db, "111", "Pizza en Miami")
        assert "Lechería" not in (reply or "") and "NACIONAL" not in (reply or "")


async def test_cinema_in_a_named_city_after_a_food_search_uses_that_city(Session, sent, monkeypatch):
    from app import cinema_whatsapp as cinema
    queries = []

    async def run(body, **kw):
        queries.append(body)
        return cinema.UNAVAILABLE

    async def quiet(*args):
        return {"mock": True}
    monkeypatch.setattr(cinema, "run_cinema_agent", run)
    monkeypatch.setattr(cinema, "send_whatsapp_message", quiet)
    monkeypatch.setattr(cinema.settings, "cinema_mcp_enabled", True)
    async with Session() as db:
        await _lecheria_food(db)
        reply = await webhook._events_route(db, "111", "Quiero ver el cine aquí en Caracas. No compres entradas.")
        assert "Caracas" in reply and "Lechería" not in reply
        assert "Ciudad explícita para esta consulta: Caracas." in queries[0]


async def test_cinema_in_that_city_after_a_food_search_keeps_the_city(Session, sent, monkeypatch):
    from app import cinema_whatsapp as cinema
    queries = []

    async def run(body, **kw):
        queries.append(body)
        return cinema.UNAVAILABLE

    async def quiet(*args):
        return {"mock": True}
    monkeypatch.setattr(cinema, "run_cinema_agent", run)
    monkeypatch.setattr(cinema, "send_whatsapp_message", quiet)
    monkeypatch.setattr(cinema.settings, "cinema_mcp_enabled", True)
    async with Session() as db:
        await _lecheria_food(db)
        reply = await webhook._events_route(db, "111", "¿Qué películas hay en esa ciudad? No compres entradas.")
        assert "Lechería" in reply
        assert "Ciudad explícita para esta consulta: Lechería." in queries[0]


def test_a_restaurant_named_after_a_city_is_still_a_business():
    from app.auth import named_business_query
    assert named_business_query("¿Dónde queda el Restaurante Valencia?")[0] == "Valencia"
    assert named_business_query("Estoy buscando dónde comer en Lechería.") is None


@pytest.mark.parametrize("written,name,state", [
    ("Cantaura", "Cantaura", "Anzoátegui"), ("tucupido", "Tucupido", "Guárico"),
    ("Santa Elena", "Santa Elena de Uairén", "Bolívar"), ("Petare", "Petare", "Miranda"),
    ("El Tocuyo", "El Tocuyo", "Lara"), ("Ureña", "Ureña", "Táchira"), ("quibor", "Quíbor", "Lara"),
    ("Cumaná", "Cumaná", "Sucre"), ("Caracas", "Caracas", "Distrito Capital"),
])
def test_every_municipality_seat_is_a_city(written, name, state):
    city = venezuela.find_city(written)
    assert city and (city.name, city.state) == (name, state)


@pytest.mark.parametrize("word", ["Cordero", "Delicias", "Libertad", "Soledad", "Colón", "Miranda"])
def test_seats_that_are_everyday_words_are_not_cities(word):
    assert venezuela.find_city(word) is None


def test_neighboring_cities_stay_distinct():
    zones = delivery.load_zones(NACIONAL_ZONES)
    pick = lambda zone, address: (delivery.zone_for_order(zones, zone, address) or {}).get("name")  # noqa: E731
    # The address decides, even when the model filled the neighboring city as the zone.
    assert pick("Barcelona", "Calle Bolívar, Puerto La Cruz") == "Puerto La Cruz"
    assert pick("Barcelona", "Av. Principal de Lechería") == "Lechería"
    # A city outside the zones is not billed as a registered one.
    assert pick("Barcelona", "Calle Sucre, Cumaná") is None
    assert pick("Lechería", "Av. Urdaneta, Caracas") is None
    # No city in the address: the zone the customer gave is kept.
    assert pick("Barcelona", "Calle 5, casa 3") == "Barcelona"


def test_agent_context_names_each_zone_state():
    r = Restaurant(name="NACIONAL Restaurante", slug="nacional", pin="0", delivery_zones=NACIONAL_ZONES)
    text = delivery.describe(r, lambda v: f"${v:.0f}")
    assert "Lechería (Anzoátegui): $2; Barcelona (Anzoátegui): $3; Puerto La Cruz (Anzoátegui): $4" in text
    assert "nunca cobres una por otra" in text


def test_street_named_after_a_city_does_not_change_the_zone():
    zones = delivery.load_zones(NACIONAL_ZONES)
    assert delivery.zone_for_order(zones, "Lechería", "Av. Barcelona, Lechería, casa 3")["name"] == "Lechería"


def test_neighborhood_zone_kept_for_an_address_in_its_city():
    zones = delivery.load_zones(json.dumps([{"name": "Centro de Lechería", "fee": 2}, {"name": "Barcelona", "fee": 3}]))
    assert delivery.zone_for_order(zones, "Centro de Lechería", "Calle 5, Lechería")["name"] == "Centro de Lechería"
    assert delivery.zone_for_order(zones, "Centro de Lechería", "Calle 5, Barcelona")["name"] == "Barcelona"


def test_the_two_santa_barbaras_are_different_cities():
    assert venezuela.find_city("Santa Bárbara del Zulia").state == "Zulia"
    assert venezuela.find_city("Santa Bárbara de Barinas").state == "Barinas"


def test_cityless_zone_gives_way_to_the_zone_the_address_names():
    zones = delivery.load_zones(json.dumps([{"name": "Centro", "fee": 2}, {"name": "Barcelona", "fee": 3}]))
    assert delivery.zone_for_order(zones, "Centro", "Calle 5, Barcelona")["name"] == "Barcelona"
    assert delivery.zone_for_order(zones, "Centro", "Calle 5, Lechería")["name"] == "Centro"
    assert delivery.zone_for_order(zones, "Centro", "Centro, Av. Barcelona, Lechería")["name"] == "Centro"


def test_longer_zone_named_in_the_address_wins_over_the_one_inside_it():
    zones = delivery.load_zones(json.dumps([{"name": "Centro", "fee": 2}, {"name": "Centro de Barcelona", "fee": 3}]))
    assert delivery.zone_for_order(zones, "Centro", "Centro de Barcelona, calle 4")["name"] == "Centro de Barcelona"


async def test_restaurants_in_that_city_after_a_food_search_stay_in_the_city(Session, sent):
    async with Session() as db:
        await _lecheria_food(db)
        reply = await webhook._events_route(db, "111", "¿Qué restaurantes hay en esa ciudad?")
        assert reply.startswith("En Lechería te puedo atender") and "Prueba" not in reply


async def test_cinema_in_this_city_after_a_food_search_keeps_the_city(Session, sent, monkeypatch):
    async with Session() as db:
        await _lecheria_food(db)
        reply = await webhook._events_route(db, "111", "¿Qué películas hay en el cine en esta ciudad?")
        assert "Lechería" in reply


async def test_a_non_food_question_about_that_city_is_not_a_food_search(Session, sent):
    async with Session() as db:
        await _lecheria_food(db)
        reply = await webhook._events_route(db, "111", "¿Allí dan clases de boxeo?")
        assert not (reply or "").startswith("En Lechería")


async def test_outside_this_city_is_not_this_city(Session, sent):
    async with Session() as db:
        await _lecheria_food(db)
        reply = await webhook._events_route(db, "111", "¿Qué restaurantes hay fuera de esta ciudad?")
        assert not (reply or "").startswith("En Lechería")


async def test_a_genre_exclusion_keeps_the_cinema_city(Session, sent):
    async with Session() as db:
        await _lecheria_food(db)
        reply = await webhook._events_route(db, "111", "¿Qué películas hay en el cine en esta ciudad que no sea de terror?")
        assert "Lechería" in reply
