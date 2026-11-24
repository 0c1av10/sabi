"""A greeting like "Habla sabi" must restart the conversation, not continue an old order.

Reported 2026-11-23: with an open NACIONAL conversation, "Habla sabi" was routed into that
business and answered as if the food order continued, instead of asking what the person wants.
"""
import pytest
from sqlalchemy import func, select

from app.models import Conversation, Customer, Restaurant


async def _open_conversation(Session, slug="nacional", phone="584140000099"):
    import app.main as m
    await m.seed_known_businesses()
    async with Session() as s:
        from scripts.seed import seed
    # nacional comes from scripts.seed; seed only what the test needs if absent
    async with Session() as s:
        r = (await s.execute(select(Restaurant).where(Restaurant.slug == slug))).scalar_one_or_none()
        if r is None:
            from scripts import seed as seedmod
            await seedmod.seed()
            r = (await s.execute(select(Restaurant).where(Restaurant.slug == slug))).scalar_one()
        cust = Customer(restaurant_id=r.id, phone=phone, name="")
        s.add(cust)
        await s.flush()
        s.add(Conversation(restaurant_id=r.id, customer_id=cust.id, status="open"))
        await s.commit()
        return r.id


@pytest.mark.asyncio
async def test_habla_sabi_closes_open_conversation_and_greets(Session, monkeypatch):
    from app.routers.webhook import _resolve
    await _open_conversation(Session)
    async with Session() as s:
        restaurant, _, reply = await _resolve(s, "584140000099", "Habla sabi")
        assert restaurant is None, "a greeting must not enter the old open conversation"
        assert reply, "a greeting gets an answer"
        assert "pollo" not in reply.lower() and "cachapa" not in reply.lower()
        open_count = (await s.execute(select(func.count()).select_from(Conversation)
                                      .where(Conversation.status == "open"))).scalar_one()
        assert open_count == 0


def test_greeting_lexicon_covers_venezuelan_openers():
    from app import concierge
    for ok in ("Habla sabi", "habla", "Habla", "Epa", "épale", "aló", "Aló sabi", "ola", "olis",
               "qué tal", "qué hay", "oye", "sabi", "saludo", "saludos", "buenas buenas",
               "Buenas noches, Sabi", "hello", "hola sabi", "holi", "hey sabi"):
        assert concierge.is_greeting(ok), ok
    # greeting-only small talk still restarts
    for ok in ("hola, ¿cómo estás?", "Habla sabi, ¿cómo estás?", "buenas, ¿qué tal?"):
        assert concierge.is_greeting(ok), ok
    # a greeting with a request is not a bare greeting: the request must be answered
    for no in ("habla con el dueño", "epa quiero pizza", "Habla sabi, quiero pizza",
               "hola quiero pizza", "quiero pastelitos", "Lechería",
               "qué hay para ver en plc", "saludos, ¿tienen delivery?"):
        assert not concierge.is_greeting(no), no


@pytest.mark.asyncio
async def test_greeting_with_request_keeps_normal_routes(Session, monkeypatch):
    """"Habla sabi, quiero pizza" names a product: it must reach that business, not restart."""
    from app.auth import restaurant_for_message
    import app.main as m
    await m.seed_known_businesses()
    async with Session() as s:
        r, _ = await restaurant_for_message(s, "584140000098", "Habla sabi, quiero pizza")
        assert r and r.slug == "bizza"
