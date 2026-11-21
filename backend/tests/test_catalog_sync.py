"""Re-reading a business's website: what changes, and the description-only sync."""
import pytest

from app.models import MenuItem, Restaurant
from app.routers import store

SITE = {"name": "NACIONAL", "tagline": "", "logo_url": "", "brand_color": "", "delivery_fee": None,
        "delivery_info": "", "delivery_zones": [], "website": "https://nacionalrestaurant.com",
        "items": [{"name": "Combo Resuelve", "price": 18.0, "category": "Promociones", "image_url": "",
                   "description": "1 pollo a la brasa + 2 acompañantes a escoger + 1 refresco de 1 litro"},
                  {"name": "Pollo Solo", "price": 14.0, "category": "Promociones", "image_url": "",
                   "description": "1 pollo a la brasa entero, solo"},
                  {"name": "Plato Nuevo", "price": 9.0, "category": "Platos", "image_url": "", "description": ""}]}


async def _nacional(db):
    r = Restaurant(name="NACIONAL Restaurante", slug="nacional", pin="0000", website="https://nacionalrestaurant.com")
    db.add(r)
    await db.flush()
    db.add(MenuItem(restaurant_id=r.id, name="Combo Resuelve", price=17.0, category="Promociones", description=""))
    db.add(MenuItem(restaurant_id=r.id, name="Pollo Solo", price=14.0, category="Promociones",
                    description="Escrito por el dueño"))
    await db.commit()
    return r


async def _menu(db, rid):
    rows = (await db.execute(MenuItem.__table__.select().where(MenuItem.restaurant_id == rid))).all()
    return {row.name: (row.price, row.description) for row in rows}


@pytest.fixture(autouse=True)
def site(monkeypatch):
    async def fake(url):
        return SITE
    monkeypatch.setattr(store, "import_site", fake)


async def test_description_sync_only_fills_empty_descriptions(Session):
    async with Session() as db:
        r = await _nacional(db)
        rid = r.id
        dry = await store.reimport(restaurant=r, db=db, mode="descriptions", dry_run=True)
        assert dry["changes"] == [{"dish": "Combo Resuelve", "field": "description", "from": "",
                                   "to": SITE["items"][0]["description"]}]
        assert (await _menu(db, rid))["Combo Resuelve"] == (17.0, "")
        r = await db.get(Restaurant, rid)
        await store.reimport(restaurant=r, db=db, mode="descriptions")
        assert await _menu(db, rid) == {"Combo Resuelve": (17.0, SITE["items"][0]["description"]),
                                      "Pollo Solo": (14.0, "Escrito por el dueño")}


async def test_full_reimport_reports_price_overwrites_and_new_dishes(Session):
    async with Session() as db:
        r = await _nacional(db)
        rid = r.id
        dry = await store.reimport(restaurant=r, db=db, dry_run=True)
        assert {(c["dish"], c["field"]) for c in dry["changes"]} == {
            ("Combo Resuelve", "price"), ("Combo Resuelve", "description"), ("Plato Nuevo", "added")}
        assert len(await _menu(db, rid)) == 2


async def test_full_dry_run_lists_delivery_pricing_it_would_fill(Session, monkeypatch):
    zones = [{"name": "Lechería", "fee": 2.0}, {"name": "Barcelona", "fee": 3.0}]
    async def fake(url):
        return {**SITE, "delivery_fee": 2.0, "delivery_zones": zones}
    monkeypatch.setattr(store, "import_site", fake)
    async with Session() as db:
        r = await _nacional(db)
        dry = await store.reimport(restaurant=r, db=db, dry_run=True)
        fields = {c["field"]: c["to"] for c in dry["changes"] if c["dish"] is None}
        assert fields == {"delivery_fee": 2.0, "delivery_zones": zones}


async def test_description_sync_skips_dishes_sharing_a_name(Session):
    async with Session() as db:
        r = await _nacional(db)
        rid = r.id
        db.add(MenuItem(restaurant_id=rid, name="Combo Resuelve", price=20.0, category="Delivery", description=""))
        await db.commit()
        dry = await store.reimport(restaurant=r, db=db, mode="descriptions", dry_run=True)
        assert dry["changes"] == []
