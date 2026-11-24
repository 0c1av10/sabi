"""Published Abruzzo's catalog and ordering context; offline, isolated test DB only."""
from collections import Counter
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from sqlalchemy import select

from app import agent, delivery
from app.known_menus import ABRUZZOS_INFO, ABRUZZOS_MENU, BIZZA_MENU
from app.models import Conversation, MenuItem, Restaurant


def test_published_catalog_and_combos():
    assert len(ABRUZZOS_MENU) == 65
    assert len({n.lower() for n, *_ in ABRUZZOS_MENU}) == 65
    assert Counter(c for _, _, c, _ in ABRUZZOS_MENU) == {
        "Pizzas": 8, "Premium": 1, "Postres": 2, "Bebidas": 24,
        "Salsas Especiales": 9, "Extras": 18, "Combos": 3,
    }
    catalog = {n: (p, c, d) for n, p, c, d in ABRUZZOS_MENU}
    assert catalog["Napolitana"][2] == "Salsa pomodoro, mozzarella de búfala, albahaca y aceite de oliva"
    assert "mantequilla de ajo" in catalog["Bastoncini"][2]
    assert all("Adicional para pizzas" in d for _, _, c, d in ABRUZZOS_MENU if c == "Extras")
    assert catalog["Extra: Galleta Caledonia"][0] == 0
    assert catalog["Promo FUDGY"][0] == 5
    assert "3 Galletas FUDGY" in catalog["Promo FUDGY"][2]
    assert catalog["PROMO SKIPY"][0] == 6.5
    assert "Nestea" in catalog["PROMO SKIPY"][2]
    assert "Elige 2" in catalog["PROMO SKIPY"][2]
    loca = catalog["PROMO LOCA"][2]
    assert catalog["PROMO LOCA"][0] == 10
    assert "2 pizzas DIFERENTES de 33 cmde cualquiera de nuestro sabores!" in loca
    assert "2 Pepperoni +$2.50" in loca and "2 Pizza de Nutella +$4" in loca
    assert "2 Bastoncini +$2.50" in loca and "2 Napolitana +$2.50" in loca
    assert "Salchicha Italiana" in loca and "confirmar" in loca


@pytest.mark.asyncio
async def test_seed_once_preserves_all_merchant_and_menu_edits(Session):
    from app.main import seed_known_businesses

    await seed_known_businesses()
    async with Session() as db:
        r = (await db.execute(select(Restaurant).where(Restaurant.slug == "abruzzos"))).scalar_one()
        assert r.name == "Pizzería Abruzzo's" and r.currency == "USD"
        assert r.website == "https://www.pizzeriaabruzzos.com/"
        assert r.pin.isdigit() and len(r.pin) == 4
        assert r.owner_phone == ""
        assert r.delivery_fee is None and delivery.zones_of(r) == []
        assert r.delivery_info == ABRUZZOS_INFO
        assert "Lechería y Los Palos Grandes: diario 12:00–23:00" in r.opening_hours
        items = (await db.execute(select(MenuItem).where(MenuItem.restaurant_id == r.id))).scalars().all()
        assert len(items) == 65
        assert {(i.name, i.price, i.category, i.description) for i in items} == set(ABRUZZOS_MENU)
        r.name = "Edited merchant"
        r.pin = "owner-pin"
        r.delivery_info = "Owner delivery terms"
        r.delivery_fee = 7
        items[0].description = "Owner description"
        items[0].price = 99
        item_id = items[0].id
        await db.commit()
    await seed_known_businesses()
    async with Session() as db:
        r = (await db.execute(select(Restaurant).where(Restaurant.slug == "abruzzos"))).scalar_one()
        assert (r.name, r.pin, r.delivery_info, r.delivery_fee) == (
            "Edited merchant", "owner-pin", "Owner delivery terms", 7)
        items = (await db.execute(select(MenuItem).where(MenuItem.restaurant_id == r.id))).scalars().all()
        assert len(items) == 65
        edited = await db.get(MenuItem, item_id)
        assert edited.description == "Owner description" and edited.price == 99


@pytest.mark.asyncio
async def test_branch_hours_shortcut_uses_published_schedule(Session):
    from app.main import seed_known_businesses

    await seed_known_businesses()
    async with Session() as db:
        r = (await db.execute(select(Restaurant).where(Restaurant.slug == "abruzzos"))).scalar_one()
        result = await agent.run_agent(db, r, Conversation(state_json="{}"), [],
                                       "¿Cuál es el horario de Lechería?")
        assert "Lechería y Los Palos Grandes: diario 12:00–23:00" in result.reply
        assert "UCAB: lun–vie 11:00–17:00; sáb–dom cerrado" in result.reply
        assert "domingo dice 00:00–22:00 (confirmar con el local)" in result.reply


def test_menu_context_empty_unavailable_and_bounded_descriptions():
    assert agent.menu_text([], (1, 1)) == ""
    item = MenuItem(name="Dish", price=2, category="Menu", available=True, description=None)
    assert agent.menu_text([item], (1, 1)) == "- Dish (Menu): $2,00 · Bs 2,00"
    item.description = "Ingredients\nwith   spaces"
    assert "Ingredients" not in agent.menu_text([item], (1, 1))
    assert "Ingredients with spaces" in agent.menu_text([item], (1, 1), details=True)
    item.description = "x" * 10000
    assert agent.menu_text([item], (1, 1), details=True).endswith("x" * 2000 + "…")
    item.available = False
    assert agent.menu_text([item], (1, 1)) == ""
    assert agent.menu_text([item], (1, 1), details=True) == ""


def test_bizza_customer_menu_keeps_compact_lines_under_whatsapp_limit():
    items = [MenuItem(name=n, price=p, category=c, description=d, available=True)
             for n, p, c, d in BIZZA_MENU]
    r = Restaurant(name="Bizza", exchange_rate=875.65, eur_rate=980.61)
    result = agent.run_mock_agent(r, items, Conversation(state_json="{}"), "menú", [])
    expected = "\n".join(
        f"- {i.name} ({i.category}): {agent.fmt_money(i.price, 875.65, 980.61)}" for i in items)
    assert agent.menu_text(items, (875.65, 980.61)) == expected
    assert "Tenemos 74 platos" in result.reply and "Pizzas" in result.reply
    assert len(result.reply) <= 4096
    category_reply = agent.run_mock_agent(r, items, Conversation(state_json="{}"), "Entradas", []).reply
    assert category_reply == "Entradas:\n" + "\n".join(
        line for line, item in zip(expected.splitlines(), items) if item.category == "Entradas")
    assert len(category_reply) <= 4096


@pytest.mark.asyncio
async def test_ordering_llm_receives_descriptions_and_unpriced_delivery(monkeypatch):
    import anthropic

    create = AsyncMock(return_value=SimpleNamespace(content=[]))
    monkeypatch.setattr(anthropic, "AsyncAnthropic", lambda **kw: SimpleNamespace(
        messages=SimpleNamespace(create=create)))
    r = Restaurant(name="Pizzería Abruzzo's", opening_hours="Por sucursal", exchange_rate=1,
                   eur_rate=1, delivery_fee=None, delivery_zones="", delivery_info=ABRUZZOS_INFO)
    items = [MenuItem(name=n, price=p, category=c, description=d, available=True)
             for n, p, c, d in ABRUZZOS_MENU]
    await agent.run_llm_agent(r, items, Conversation(state_json="{}"), [], "¿Qué incluye PROMO LOCA?")
    context = create.call_args.kwargs["system"]
    assert "Salsa de tomate, mozzarella fresca, albahaca" in context
    assert "2 pizzas DIFERENTES de 33 cmde" in context
    assert "Nestea" in context and "2 Pepperoni +$2.50" in context
    assert ABRUZZOS_INFO in context
    assert "no inventes un monto" in context
    assert "El costo final lo calcula la tienda desde la dirección" in context
    assert "NO tarifas finales por zona" in context
    assert "Lechería: $2" in context and "Paseo Colón: $2" in context and "Santa Fe: $3" in context
    assert "Boyacá" in context and "Los Samanes" in context
    assert "Para las otras sucursales no hay tarifa de delivery publicada" in context
    assert "WhatsApp +584129467782" in context and "UCAB" in context
    assert delivery.zones_of(r) == [] and r.delivery_fee is None
    assert "Costo de delivery: gratis" not in context
