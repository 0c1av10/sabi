"""Menu follow-ups use the same routing pipeline as incoming WhatsApp messages."""
from unittest.mock import AsyncMock

import pytest
from sqlalchemy import select

from app import concierge, service
from app.models import Conversation, Customer, MenuItem, Message, Restaurant


@pytest.mark.parametrize("merchant,followup,expected", [
    ("beijing", "combos chinos", "ARROZ ESPECIAL Y CHOP SUEY"),
    ("beijing", "¿COMBOS CHINOS?", "ARROZ ESPECIAL Y CHOP SUEY"),
    ("beijing", "entradas japonesas", "EBY FUJI"),
    ("beijing", "cotidiano deluxe chino", "COTIDIANO DELUXE CHINO"),
    ("bizza", "pizzas", "MARGARITA"),
])
async def test_menu_followup_stays_with_merchant(Session, client, monkeypatch, merchant, followup, expected):
    from app.main import seed_known_businesses
    await seed_known_businesses()
    monkeypatch.setattr(service, "refresh_rates", AsyncMock())
    first = await client.post("/webhook/simulate", json={"phone": "111", "text": f"menu [sabi:{merchant}]"})
    assert "categorías" in first.json()["reply"]
    reply = AsyncMock(wraps=concierge.reply)
    monkeypatch.setattr(concierge, "reply", reply)
    response = await client.post("/webhook/simulate", json={"phone": "111", "text": followup})
    assert response.status_code == 200
    assert expected in response.json()["reply"]
    reply.assert_not_awaited()
    async with Session() as db:
        messages = (await db.execute(select(Message.body).join(Conversation).join(
            Restaurant, Conversation.restaurant_id == Restaurant.id).where(
                Restaurant.slug == merchant, Message.direction == "inbound"))).scalars().all()
        assert followup in messages


@pytest.mark.parametrize("merchant,followup", [
    ("beijing", "quiero comida china"),
    ("beijing", "recomiéndame algo chino"),
    ("bizza", "recomiéndame comida china con bebidas"),
    ("bizza", "quiero comida china con bebidas"),
    ("bizza", "recomiéndame comida china con pizzas"),
    ("beijing", "recomiéndame comida italiana con bebidas"),
])
async def test_new_cuisine_request_still_reaches_concierge(Session, client, monkeypatch, merchant, followup):
    from app.main import seed_known_businesses
    await seed_known_businesses()
    monkeypatch.setattr(service, "refresh_rates", AsyncMock())
    await client.post("/webhook/simulate", json={"phone": "111", "text": f"menu [sabi:{merchant}]"})
    reply = AsyncMock(wraps=concierge.reply)
    monkeypatch.setattr(concierge, "reply", reply)
    response = await client.post("/webhook/simulate", json={"phone": "111", "text": followup})
    assert response.status_code == 200
    reply.assert_awaited_once()
    async with Session() as db:
        messages = (await db.execute(select(Message.body).where(Message.direction == "inbound"))).scalars().all()
        assert followup not in messages


@pytest.mark.parametrize("state", ["no_conversation", "empty_menu", "other_menu", "closed"])
async def test_menu_match_requires_current_open_merchants_menu(Session, client, monkeypatch, state):
    monkeypatch.setattr(service, "refresh_rates", AsyncMock())
    async with Session() as db:
        active = Restaurant(name="Local activo", slug="active", pin="fixture")
        other = Restaurant(name="Otro local", slug="other", pin="fixture")
        db.add_all([active, other])
        await db.flush()
        if state != "empty_menu":
            db.add(MenuItem(restaurant_id=other.id if state == "other_menu" else active.id,
                            name="Plato", category="Combos chinos", price=10))
        if state != "no_conversation":
            customer = Customer(restaurant_id=active.id, phone="111")
            db.add(customer)
            await db.flush()
            db.add(Conversation(restaurant_id=active.id, customer_id=customer.id,
                                status="closed" if state == "closed" else "open"))
        await db.commit()
    reply = AsyncMock(wraps=concierge.reply)
    monkeypatch.setattr(concierge, "reply", reply)
    response = await client.post("/webhook/simulate", json={"phone": "111", "text": "combos chinos"})
    assert response.status_code == 200
    reply.assert_awaited_once()
