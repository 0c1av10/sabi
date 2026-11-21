"""Regression tests for the WhatsApp continuity failures reported on 2026-11-20:
Sabi lost the active order after ~30 min, asked people to repeat short follow-ups,
and gave a different random restaurant list on every ask."""
import json
import sys
import types

from sqlalchemy import select

from app import agent, concierge, conversation_focus as focus
from app.models import Conversation, Customer, MenuItem, Message, Restaurant
from app.routers import webhook


async def _restaurant(db, name, slug, phone="111"):
    r = Restaurant(name=name, slug=slug, pin="test")
    db.add(r)
    await db.flush()
    c = Customer(restaurant_id=r.id, phone=phone)
    db.add(c)
    await db.flush()
    db.add(Conversation(restaurant_id=r.id, customer_id=c.id, status="open"))
    await db.commit()
    return r


async def test_open_conversation_keeps_restaurant_when_focus_expired(Session):
    """"Si dame ese pero pídelo mañana a las 9 am" 33 min after the last message must
    stay with the restaurant of the open conversation, not fall back to the welcome."""
    async with Session() as db:
        r = await _restaurant(db, "MC Racuchos", "mc-racuchos")
        restaurant, _, reply = await webhook._resolve(
            db, "111", "Si dame ese pero pídelo mañana a las 9 am")
        assert restaurant is not None and restaurant.id == r.id and reply is None


async def test_open_conversation_without_focus_keeps_order_followups(Session):
    async with Session() as db:
        r = await _restaurant(db, "NACIONAL Restaurante", "nacional")
        restaurant, _, reply = await webhook._resolve(db, "111", "Agrégale un refresco")
        assert restaurant is not None and restaurant.id == r.id and reply is None
        restaurant, _, reply = await webhook._resolve(db, "111", "Sera delivery")
        assert restaurant is not None and restaurant.id == r.id and reply is None


async def test_place_focus_still_blocks_restaurant_stickiness(Session):
    """An unresolved-place task owns the follow-ups; it never inherits an open restaurant."""
    async with Session() as db:
        await _restaurant(db, "Bizza", "bizza")
        await focus.save(db, "111", domain="place", entity="Abruzzos", city="Valencia")
        restaurant, _, _ = await webhook._resolve(db, "111", "Y cuál es la mejor")
        assert restaurant is None


async def test_full_catalog_ask_beats_open_conversation_stickiness(Session):
    """"Dame todos los restaurantes que tengas" is a concierge question even mid-order."""
    async with Session() as db:
        r = await _restaurant(db, "NACIONAL Restaurante", "nacional")
        db.add(Restaurant(name="Bizza", slug="bizza", pin="x"))
        await db.commit()
        restaurant, _, reply = await webhook._resolve(
            db, "111", "Dame todos los restaurantes que tengas")
        assert restaurant is None
        assert "Bizza" in reply and "NACIONAL Restaurante" in reply


async def test_full_catalog_listing_is_complete_and_stable(Session):
    """"Dame todos los restaurantes que tengas" lists every business, in a stable order."""
    async with Session() as db:
        for name, slug in (("Bizza", "bizza"), ("MC Racuchos", "mc-racuchos"),
                           ("NACIONAL Restaurante", "nacional")):
            db.add(Restaurant(name=name, slug=slug, pin="x"))
        await db.commit()
        first = await concierge.recommendations(db, body="Dame todos los restaurantes que tengas")
        second = await concierge.recommendations(db, body="Dame todos los restaurantes que tengas")
        assert first == second
        for name in ("Bizza", "MC Racuchos", "NACIONAL Restaurante"):
            assert name in first


async def test_two_suggestions_still_short(Session):
    async with Session() as db:
        for name, slug in (("Bizza", "bizza"), ("MC Racuchos", "mc-racuchos"),
                           ("NACIONAL Restaurante", "nacional")):
            db.add(Restaurant(name=name, slug=slug, pin="x"))
        await db.commit()
        text = await concierge.recommendations(db, body="Tengo hambre")
        assert text.count("•") <= 2


async def test_bare_city_answer_completes_pending_place(Session):
    """After "¿En qué ciudad queda X?", a bare "Lecheria" is the answer, not a new query."""
    async with Session() as db:
        await focus.save(db, "111", domain="place", entity="Abruzzos")
        reply = await focus.city_reply(db, "111", "Lecheria")
        assert reply and "Lechería" in reply
        assert (await focus.get(db, "111")).city == "Lechería"


async def test_restaurant_mention_is_not_taken_as_city(Session):
    async with Session() as db:
        db.add(Restaurant(name="Bizza", slug="bizza", pin="x"))
        await db.commit()
        await focus.save(db, "111", domain="place", entity="Abruzzos")
        assert await focus.city_reply(db, "111", "Bizza") is None
        assert (await focus.get(db, "111")).city == ""


async def test_food_word_is_not_taken_as_city(Session):
    async with Session() as db:
        await focus.save(db, "111", domain="place", entity="Abruzzos")
        assert await focus.city_reply(db, "111", "pizza") is None


async def _nacional(db, phone="111"):
    r = Restaurant(name="NACIONAL Restaurante", slug="nacional", pin="test",
                   delivery_zones='[{"name": "Lechería", "fee": 2.0}, {"name": "Barcelona", "fee": 3.0}]')
    db.add(r)
    await db.flush()
    db.add(MenuItem(restaurant_id=r.id, name="Pabellón criollo", price=13.0, category="Platos"))
    db.add(MenuItem(restaurant_id=r.id, name="INDIVIDUAL 3 piezas", price=4.90, category="Combos"))
    db.add(MenuItem(restaurant_id=r.id, name="INDIVIDUAL 5 piezas", price=7.30, category="Combos"))
    db.add(MenuItem(restaurant_id=r.id, name="Refresco", price=2.0, category="Bebidas"))
    await db.commit()
    return r


async def test_ambiguous_ese_asks_and_keeps_everything_else(Session):
    """"Si dame ese pero pídelo mañana a las 9 am" after two combos were offered: Sabi asks
    which combo, never picks one, and keeps the requested time in the draft notes."""
    from app.service import handle_inbound_message
    async with Session() as db:
        r = await _nacional(db)
        c = Customer(restaurant_id=r.id, phone="111")
        db.add(c)
        await db.flush()
        conv = Conversation(restaurant_id=r.id, customer_id=c.id, status="open", state_json="{}")
        db.add(conv)
        await db.flush()
        db.add(Message(conversation_id=conv.id, direction="outbound",
                       body="Estos son los combos: INDIVIDUAL 3 piezas: $4,90 · INDIVIDUAL 5 piezas: $7,30"))
        await db.commit()
        reply = await handle_inbound_message(db, r, "111", "Si dame ese pero pídelo mañana a las 9 am")
        assert "¿Cuál" in reply and "INDIVIDUAL 3 piezas" in reply and "INDIVIDUAL 5 piezas" in reply
        await db.refresh(conv)
        draft = json.loads(conv.state_json)["draft"]
        assert draft["items"] == []
        assert "mañana a las 9 am" in draft["notes"]


async def test_single_offered_option_is_what_ese_means(Session):
    from app.service import handle_inbound_message
    async with Session() as db:
        r = await _nacional(db)
        c = Customer(restaurant_id=r.id, phone="111")
        db.add(c)
        await db.flush()
        conv = Conversation(restaurant_id=r.id, customer_id=c.id, status="open", state_json="{}")
        db.add(conv)
        await db.flush()
        db.add(Message(conversation_id=conv.id, direction="outbound",
                       body="Te recomiendo el Pabellón criollo, un clásico de la casa."))
        await db.commit()
        reply = await handle_inbound_message(db, r, "111", "Si, dame ese")
        await db.refresh(conv)
        draft = json.loads(conv.state_json)["draft"]
        assert [i["name"] for i in draft["items"]] == ["Pabellón criollo"]
        assert "Pabellón criollo" in reply


async def test_fields_survive_fragmented_messages(Session):
    """Fragmented sends (plato, luego "delivery", luego la zona) accumulate into one draft."""
    from app.service import handle_inbound_message
    async with Session() as db:
        r = await _nacional(db)
        await handle_inbound_message(db, r, "111", "quiero 1 pabellón criollo")
        await handle_inbound_message(db, r, "111", "delivery")
        await handle_inbound_message(db, r, "111", "Lechería")
        conv = (await db.execute(select(Conversation))).scalars().first()
        draft = json.loads(conv.state_json)["draft"]
        assert [i["name"] for i in draft["items"]] == ["Pabellón criollo"]
        assert draft["order_type"] == "delivery" and draft["delivery_zone"] == "Lechería"
        reply = await handle_inbound_message(db, r, "111", "y agrégale un refresco")
        await db.refresh(conv)
        draft = json.loads(conv.state_json)["draft"]
        names = [i["name"] for i in draft["items"]]
        assert "Pabellón criollo" in names and "Refresco" in names
        assert draft["order_type"] == "delivery" and draft["delivery_zone"] == "Lechería"


class _ToolUse:
    type = "tool_use"

    def __init__(self, data):
        self.input = data


class _FakeAnthropic:
    """Records the call and returns whatever tool input the test seeds."""
    calls = {}
    seeded = {}

    def __init__(self, api_key=""):
        class Messages:
            async def create(self, **kwargs):
                _FakeAnthropic.calls = kwargs

                class Resp:
                    content = [_ToolUse(_FakeAnthropic.seeded)]
                return Resp()
        self.messages = Messages()


async def _run_fake_llm(Session, monkeypatch, seeded):
    mod = types.ModuleType("anthropic")
    mod.AsyncAnthropic = _FakeAnthropic
    mod.APIError = Exception
    monkeypatch.setitem(sys.modules, "anthropic", mod)
    from app.config import settings
    monkeypatch.setattr(settings, "anthropic_api_key", "test-key")
    _FakeAnthropic.seeded = seeded
    async with Session() as db:
        r = Restaurant(name="Bizza", slug="bizza", pin="x")
        db.add(r)
        await db.flush()
        db.add(MenuItem(restaurant_id=r.id, name="Pizza Margarita", price=10, category="Pizzas"))
        c = Customer(restaurant_id=r.id, phone="111")
        db.add(c)
        await db.flush()
        conv = Conversation(restaurant_id=r.id, customer_id=c.id, state_json="{}")
        db.add(conv)
        await db.commit()
        return await agent.run_agent(db, r, conv, [("inbound", "Y bizza?")], "Y bizza?")


async def test_empty_llm_reply_falls_back_to_grounded_offer(Session, monkeypatch):
    """An empty model reply becomes a useful grounded message, never a bare "¿Me repites?"."""
    result = await _run_fake_llm(Session, monkeypatch, {})
    assert result.reply
    assert "repites" not in result.reply
    assert "Bizza" in result.reply


async def test_first_restaurant_message_gets_general_chat_context(Session, monkeypatch):
    """The first message routed to a business carries a note that the client may be
    continuing a general Sabi conversation, so short messages are not read in a void."""
    result = await _run_fake_llm(Session, monkeypatch,
                                 {"reply": "Claro, ¿qué te provoca?", "action": "continue"})
    assert result.reply == "Claro, ¿qué te provoca?"
    assert "conversación general" in _FakeAnthropic.calls["system"]


async def test_general_chat_topic_content_reaches_the_model(Session, monkeypatch):
    """The actual content of the general exchange (the offered businesses), not just a
    generic note, is part of the model context when the client picks one."""
    from app import memory
    async with Session() as db:
        await memory.note(db, "111", topic="tu pedido en NACIONAL Restaurante (recomendación de locales: MC Racuchos, Bizza)")
    await _run_fake_llm(Session, monkeypatch, {"reply": "ok", "action": "continue"})
    system = _FakeAnthropic.calls["system"]
    assert "MC Racuchos" in system and "recomendación de locales" in system
