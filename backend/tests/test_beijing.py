"""Beijing's published menus and unknown delivery pricing. Offline fixtures only."""
import json
from collections import Counter
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from sqlalchemy import select

from app.agent import (delivery_context, menu_text, run_llm_agent, run_mock_agent,
                       summarize_order)
from app.known_menus import BEIJING_MENU
from app.models import Conversation, MenuItem, Restaurant


COUNTS = {
    "Arroces": 10, "Bebidas": 16, "Carnes": 13, "Chop Suey": 7,
    "Chow Mein": 6, "Combos chinos": 20, "Ensaladas": 6,
    "Entradas chinas": 5, "Entradas japonesas": 25,
    "Express — Línea Cotidiana": 10, "Express — Ofertas": 10,
    "Lo Mein": 7, "Maki Sushi": 45, "Mei Fan": 3, "Menú Infantil": 4,
    "Parrilla Japonesa": 1, "Plato de Degustación": 2, "Poke Bar": 3,
    "Postres": 5, "Promos chinas": 2, "Promos japonesas": 3,
    "Servicios": 11, "Sopas": 5, "Sushi Burger": 3,
}


@pytest.fixture
def beijing():
    from app.main import KNOWN_BUSINESSES
    seed = next(b for b in KNOWN_BUSINESSES if b["slug"] == "beijing")
    restaurant = Restaurant(
        name=seed["name"], slug=seed["slug"], pin="fixture",
        delivery_fee=None, delivery_zones="", delivery_info=seed["delivery_info"],
        opening_hours=seed["opening_hours"], exchange_rate=100, eur_rate=110)
    items = [MenuItem(id=i, name=n, price=p, category=c, description=d, available=True)
             for i, (n, p, c, d) in enumerate(BEIJING_MENU, 1)]
    return restaurant, items


def test_complete_menu_prices_and_combos():
    assert len(BEIJING_MENU) == 222
    assert Counter(c for _, _, c, _ in BEIJING_MENU) == COUNTS
    assert len({n.casefold() for n, *_ in BEIJING_MENU}) == len(BEIJING_MENU)
    assert all(0 < price < 100 for _, price, _, _ in BEIJING_MENU)
    assert all(desc for _, _, cat, desc in BEIJING_MENU
               if cat.startswith(("Combos", "Promos")) or cat == "Express — Ofertas")
    by_name = {n: (p, d) for n, p, _, d in BEIJING_MENU}
    assert by_name["LO MEIN CON CAMARONES"][0] == 13
    assert by_name["SOPA WONTON MEIN ESPECIAL"][0] == 14
    assert by_name["COTIDIANO ARROZ POLLO Y CAMARONES"][0] == 4.99
    price, desc = by_name["BEIJING INDIVIDUAL CHINO"]
    assert price == 12
    assert desc == (
        "ELIGE 1 PROTEÍNA Y 2 ACOMPAÑANTES. INCLUYE UN REFRESCO DE 12 OZ "
        "PROTEÍNAS (ELIGE UNA): POLLO AGRIDULCE (5 UND); POLLO A LA MIEL (150 GRS); "
        "CERDO SAL Y PIMIENTA (120 GRS); CERDO EN SALSA DE OSTRAS (150 GRS); "
        "LOMO DE RES EN SALSA DE OSTRAS (150 GRS). ACOMPAÑANTES (ELIGE DOS): "
        "ARROZ ESPECIAL (300 GRS); ARROZ CON CAMARÓN (300 GRS); CHOP SUEY (200 GRS); "
        "PAPAS FRITAS (150 GRS); LUMPIA (1 UND); CROQUETAS DE POLLO Y TOCINETA (3 UND); "
        "WONTON DE POLLO FRITO (3 UND); LO MEIN (300 GRS); POLLO CRISPY (150 GRS).")
    assert "2 REFRESCOS DE 12 OZ" in by_name["SENSU MAKI"][1]
    assert "ROLLS (ELIGE DOS): DINAMITA ROLL" in by_name["SENSU MAKI"][1]
    assert "SUSHI PIZZA MIXTA" in by_name["SENSU MAKI"][1]
    assert "4 REFRESCOS DE 12 OZ" in by_name["CATA DE GEISHAS"][1]
    assert "ROLLS (ELIGE CUATRO)" in by_name["CATA DE GEISHAS"][1]
    promo = by_name["PROMO BEIJING JAPONESA I"][1]
    assert "20 piezas de Maki Sushi (2 roles a elegir)" in promo
    assert "croquetas de atún o gyozas de cerdo" in promo
    assert "1 refresco Pepsi de 1 litro" in promo
    assert "El refresco no aplica en mesa" in promo


@pytest.mark.asyncio
async def test_seed_and_public_menu_keep_full_descriptions(Session, client):
    from app.main import seed_known_businesses
    await seed_known_businesses()
    async with Session() as db:
        r = (await db.execute(select(Restaurant).where(Restaurant.slug == "beijing"))).scalar_one()
        assert r.website == "https://www.beijingrestaurante.com"
        assert r.delivery_fee is None and not r.delivery_zones
        assert r.owner_phone == ""  # Published contact is not an authenticated owner.
        assert "0412-6035277" in r.delivery_info
        assert "Delivery a toda Caracas, Barquisimeto y Lechería" in r.delivery_info
        assert "no publica tarifas" in r.delivery_info
        assert "Los Naranjos" in r.opening_hours
        items = (await db.execute(select(MenuItem).where(MenuItem.restaurant_id == r.id))).scalars().all()
        assert {(i.name, i.price, i.category, i.description) for i in items} == set(BEIJING_MENU)
        text = menu_text(items, (100, 110))
        assert "ELIGE 1 PROTEÍNA Y 2 ACOMPAÑANTES" in text
        assert "POLLO CRISPY (150 GRS)" in text
        items[0].description = "Edición del local"
        await db.commit()
        edited_id = items[0].id
    await seed_known_businesses()
    async with Session() as db:
        merchants = (await db.execute(select(Restaurant).where(Restaurant.slug == "beijing"))).scalars().all()
        assert len(merchants) == 1
        assert (await db.get(MenuItem, edited_id)).description == "Edición del local"
    response = await client.get("/api/store/beijing")
    assert response.status_code == 200
    body = response.json()
    assert body["delivery_fee"] is None and body["delivery_zones"] == []
    assert len(body["menu"]) == 222
    combo = next(i for i in body["menu"] if i["name"] == "BEIJING INDIVIDUAL CHINO")
    assert "POLLO CRISPY (150 GRS)" in combo["description"]


def test_menu_text_compact_full_description_and_unavailable():
    desc = "ELIGE 1 PROTEÍNA\n Y 2 ACOMPAÑANTES. " + "opciones " * 40 + "REFRESCO 12 OZ"
    items = [MenuItem(name="Combo", price=12, category="Promos", description=desc, available=True),
             MenuItem(name="Agotado", price=1, category="Promos", description="Oculto", available=False)]
    text = menu_text(items, (100, 110))
    assert text == "- Combo (Promos): $12,00 · Bs 1.200,00 — " + " ".join(desc.split())
    assert len(text.splitlines()) == 1


@pytest.mark.parametrize("description", ["", None, "   \n "])
def test_menu_text_without_description(description):
    item = MenuItem(name="Plato", category="General", price=5, available=True, description=description)
    assert menu_text([item], (100, 110)) == "- Plato (General): $5,00 · Bs 500,00"
    assert menu_text([], (100, 110)) == ""


def test_unknown_delivery_context_and_mock_order(beijing):
    r, items = beijing
    context = delivery_context(r, (100, 110))
    assert "no definido" in context and "no inventes un monto" in context
    assert "debe confirmarse con el restaurante" in context
    assert "gratis" not in context.lower() and "$0" not in context
    draft = {"items": [{"name": "BEIJING INDIVIDUAL CHINO", "quantity": 1}],
             "order_type": "delivery", "address": "La Tahona", "notes": ""}
    conv = Conversation(state_json=json.dumps({"draft": draft, "upsold": True}))
    result = run_mock_agent(r, items, conv, "lo dejamos así")
    assert result.action == "ask_confirm"
    assert "Delivery — costo por confirmar con el restaurante (no incluido)" in result.reply
    assert "Subtotal (sin delivery): $12,00" in result.reply
    assert "Total:" not in result.reply
    assert "gratis" not in result.reply.lower() and "$0" not in result.reply


@pytest.mark.asyncio
async def test_llm_context_and_confirmation_unknown_delivery(beijing, monkeypatch):
    import anthropic
    r, items = beijing
    order = {"items": [{"name": "BEIJING INDIVIDUAL CHINO", "quantity": 1}],
             "order_type": "delivery", "address": "La Tahona", "notes": ""}
    create = AsyncMock(return_value=SimpleNamespace(content=[SimpleNamespace(
        type="tool_use", input={"reply": "Total con delivery gratis", "action": "ask_confirm", "order": order})]))
    monkeypatch.setattr(anthropic, "AsyncAnthropic", lambda **_: SimpleNamespace(
        messages=SimpleNamespace(create=create)))
    result = await run_llm_agent(r, items, Conversation(state_json="{}"), [], "confirmar pedido")
    prompt = create.call_args.kwargs["system"]
    assert "ELIGE 1 PROTEÍNA Y 2 ACOMPAÑANTES" in prompt
    assert "WONTON DE POLLO FRITO (3 UND)" in prompt
    assert "INCLUYE UN REFRESCO DE 12 OZ" in prompt
    assert "Costo de delivery: no definido" in prompt
    assert "nunca lo presentes como cero o gratis" in prompt
    assert result.action == "ask_confirm"
    assert "Subtotal (sin delivery): $12,00" in result.reply
    assert "costo por confirmar con el restaurante" in result.reply
    assert "gratis" not in result.reply and "Total:" not in result.reply


@pytest.mark.parametrize("order_type,fee,pending,label,total", [
    ("retiro", 0, True, "Total", 12),
    ("delivery", 0, True, "Subtotal (sin delivery)", 12),
    ("delivery", 2, False, "Total", 14),
    ("delivery", 0, False, "Total", 12),
])
def test_order_totals_known_unknown_and_pickup(beijing, order_type, fee, pending, label, total):
    _, items = beijing
    order = {"items": [{"name": "BEIJING INDIVIDUAL CHINO", "quantity": 1}], "order_type": order_type}
    text, amount = summarize_order(order, {i.name.lower(): i for i in items}, (100, 110), fee, pending)
    assert amount == total
    assert f"{label}: ${total},00" in text
    assert ("costo por confirmar" in text) == (pending and order_type == "delivery")


def test_empty_order_does_not_invent_items():
    text, amount = summarize_order({"items": [{"name": "Inexistente", "quantity": 1}]}, {}, (100, 110))
    assert amount == 0 and "Inexistente" not in text
