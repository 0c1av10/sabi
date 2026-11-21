from types import SimpleNamespace

import pytest
from sqlalchemy import select

from app import delivery
from app.agent import delivery_context, fmt_money, menu_text, rates_of, run_llm_agent, run_mock_agent, summarize_order
from app.main import apply_business_pins, seed_known_businesses
from app.models import Conversation, MenuItem, Restaurant


ZONES = [
    {"name": "Lechería · Zona 1", "fee": 2.50},
    {"name": "Lechería · Zona 2", "fee": 3.50},
    {"name": "Barcelona", "fee": 4.00},
    {"name": "Puerto La Cruz", "fee": 4.00},
]
CEVICHES = "Cubos de pescado marinados en leche de tigre de ají, coco y parchita."
CROQUETAS = "Croquetas fluidas de cordero, morcilla y pescado."
PARRILLA = "Cecina de res, muslo de pollo, baby back ribs, chorizo de ajo y morcilla."


async def get_catalog(session, slug):
    restaurant = (await session.scalars(select(Restaurant).where(Restaurant.slug == slug))).one()
    items = (await session.scalars(select(MenuItem).where(MenuItem.restaurant_id == restaurant.id))).all()
    return restaurant, {item.name: item for item in items}


@pytest.mark.asyncio
async def test_seed_published_oura_data_and_preserves_edits(Session):
    await seed_known_businesses()
    async with Session() as session:
        restaurant, items = await get_catalog(session, "oura")
        assert restaurant.name == "OURA" and restaurant.currency == "EUR"
        assert restaurant.website == "https://ourarest.netlify.app/"
        assert restaurant.email == "hola@ourarest.com"
        assert restaurant.owner_phone == ""
        assert "+58 424-833-2553" in restaurant.tagline
        assert "Precios incluyen IVA · No incluyen el 10% de servicio." in restaurant.tagline
        assert "Viernes — Sábado 12:00 — 01:00" in restaurant.opening_hours
        assert len(items) == 131 and all(item.available for item in items.values())
        assert len({item.category for item in items.values()}) == 20
        assert items["Trío de Ceviches"].description == CEVICHES
        assert items["Trío de Croquetas"].description == CROQUETAS
        assert items["Parrilla Especial Oura (2 pax)"].description == PARRILLA
        assert items["Parrilla Especial Oura (4 pax)"].description == PARRILLA
        assert items["Parrilla Mar y Tierra (2 pax)"].description == (
            "Mariscos a la parrilla, pechuga de pollo, lomito, chorizo, papas fritas y tostones."
        )
        assert delivery.zones_of(restaurant) == ZONES
        assert "Casco central, calle Arismendi, hasta Plaza Mayor, hasta R16" in restaurant.delivery_info
        assert "Casa Bote, Las Villas, Las Garzas, Colinas del Neverí, Cerro El Morro" in restaurant.delivery_info
        items["Trío de Ceviches"].price = 17
        restaurant.delivery_zones = ""
        await session.commit()
        pin = restaurant.pin

    await seed_known_businesses()
    async with Session() as session:
        restaurant, items = await get_catalog(session, "oura")
        assert len(items) == 131 and items["Trío de Ceviches"].price == 17
        assert restaurant.pin == pin and delivery.zones_of(restaurant) == []


@pytest.mark.asyncio
async def test_oura_store_and_panel_tenant_isolation(Session, client, monkeypatch):
    from app import main

    monkeypatch.setattr(main.settings, "business_pins", "oura:claveoura,bizza:clavebizza")
    await seed_known_businesses()
    await apply_business_pins()
    async with Session() as session:
        _, other_items = await get_catalog(session, "bizza")
        other_id = next(iter(other_items.values())).id
        oura, _ = await get_catalog(session, "oura")
        oura.bcv_auto = False
        await session.commit()

    store = (await client.get("/api/store/oura")).json()
    assert store["currency"] == "EUR" and store["delivery_zones"] == ZONES
    trio = next(item for item in store["menu"] if item["name"] == "Trío de Ceviches")
    assert trio["price"] == 15.99 and trio["description"] == CEVICHES
    assert (await client.post("/api/auth/login", json={"slug": "oura", "pin": "clavebizza"})).status_code == 401
    login = await client.post("/api/auth/login", json={"slug": "oura", "pin": "claveoura"})
    assert login.status_code == 200
    headers = {"X-Sabi-Token": login.json()["token"]}
    assert len((await client.get("/api/menu", headers=headers)).json()) == 131
    assert (await client.delete(f"/api/menu/{other_id}", headers=headers)).status_code == 404

    order = await client.post("/api/store/oura/orders", json={
        "name": "Cliente de prueba", "phone": "584120000000", "order_type": "delivery",
        "delivery_zone": "Lechería · Zona 2", "address": "Dirección de prueba",
        "items": [{"menu_item_id": trio["id"], "quantity": 1}],
    })
    assert order.status_code == 200
    assert order.json()["total"] == pytest.approx(19.49)


@pytest.mark.asyncio
async def test_oura_mock_and_llm_know_contents_and_native_prices(Session, monkeypatch):
    import anthropic

    await seed_known_businesses()
    async with Session() as session:
        restaurant, items = await get_catalog(session, "oura")
        bizza, _ = await get_catalog(session, "bizza")
    available = list(items.values())
    rates = rates_of(restaurant)
    conv = Conversation(state_json="{}")
    result = run_mock_agent(restaurant, available, conv, "¿qué incluye el trío de ceviches?")
    assert result.reply == f"*Trío de Ceviches* — €15,99. {CEVICHES}"
    assert result.action == "continue" and result.order is None and result.state == {}
    assert f"€15,99 — {CEVICHES}" in menu_text(available, rates)
    assert "$15,99 · Bs " in fmt_money(15.99, *rates_of(bizza))
    for zone, amount in zip(ZONES, ("€2,50", "€3,50", "€4,00", "€4,00"), strict=True):
        assert f"{zone['name']}: {amount}" in delivery_context(restaurant, rates)
        assert delivery.fee_for(restaurant, "delivery", zone["name"]) == zone["fee"]

    summary, total = summarize_order({
        "items": [{"name": "Trío de Ceviches", "quantity": 1}],
        "order_type": "delivery", "delivery_zone": "Lechería · Zona 1",
    }, {name.lower(): item for name, item in items.items()}, rates, 2.50)
    assert total == pytest.approx(18.49)
    assert "Delivery (Lechería · Zona 1) — €2,50" in summary and "Total: €18,49" in summary
    assert "Bs" not in summary and "$" not in summary

    async def create(**kwargs):
        prompt = kwargs["system"]
        assert CEVICHES in prompt and PARRILLA in prompt
        assert "Lechería · Zona 1: €2,50" in prompt
        assert "Expresa los precios en euros" in prompt and "Nunca muestres euros" not in prompt
        return SimpleNamespace(content=[SimpleNamespace(type="tool_use", input={"reply": CEVICHES})])

    monkeypatch.setattr(anthropic, "AsyncAnthropic", lambda **_: SimpleNamespace(
        messages=SimpleNamespace(create=create),
    ))
    assert (await run_llm_agent(restaurant, available, conv, [], "¿qué incluye el trío de ceviches?")).reply == CEVICHES
