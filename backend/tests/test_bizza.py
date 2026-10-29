"""Bizza onboarding: idempotent seed, exact menu, PIN access and tenant isolation. Offline."""
import pytest
from sqlalchemy import func, select

from app.known_menus import BIZZA_MENU
from app.models import MenuItem, Restaurant


async def _seed(Session, monkeypatch, pins=""):
    import app.main as m
    monkeypatch.setattr(m.settings, "business_pins", pins)
    await m.seed_known_businesses()
    await m.apply_business_pins()


def test_menu_data_is_clean():
    assert len(BIZZA_MENU) == 74
    assert len({c for _, _, c, _ in BIZZA_MENU}) == 9
    assert all(price > 0 for _, price, _, _ in BIZZA_MENU)
    assert len({n for n, *_ in BIZZA_MENU}) == len(BIZZA_MENU)


@pytest.mark.asyncio
async def test_seed_creates_bizza_without_inventing_contacts(Session, monkeypatch):
    await _seed(Session, monkeypatch)
    async with Session() as s:
        r = (await s.execute(select(Restaurant).where(Restaurant.slug == "bizza"))).scalar_one()
        assert r.name == "Bizza" and r.website == "https://bizza.tastio.club/menu"
        assert r.owner_phone == "" and r.opening_hours == "" and r.delivery_info == ""
        n = (await s.execute(select(func.count()).select_from(MenuItem).where(MenuItem.restaurant_id == r.id))).scalar_one()
        assert n == 74


@pytest.mark.asyncio
async def test_seed_is_idempotent_and_keeps_edits(Session, monkeypatch):
    await _seed(Session, monkeypatch)
    async with Session() as s:
        r = (await s.execute(select(Restaurant).where(Restaurant.slug == "bizza"))).scalar_one()
        item = (await s.execute(select(MenuItem).where(MenuItem.restaurant_id == r.id))).scalars().first()
        item.price = 99.0
        r.owner_phone = "+0000"
        await s.commit()
    await _seed(Session, monkeypatch)
    async with Session() as s:
        assert (await s.execute(select(func.count()).select_from(Restaurant).where(Restaurant.slug == "bizza"))).scalar_one() == 1
        assert (await s.execute(select(func.count()).select_from(MenuItem))).scalar_one() == 74 + 12  # + MC Racuchos
        r = (await s.execute(select(Restaurant).where(Restaurant.slug == "bizza"))).scalar_one()
        assert r.owner_phone == "+0000"
        assert 99.0 in [i.price for i in (await s.execute(select(MenuItem).where(MenuItem.restaurant_id == r.id))).scalars()]


@pytest.mark.asyncio
async def test_store_endpoint_and_other_businesses_untouched(Session, client, monkeypatch):
    await _seed(Session, monkeypatch)
    body = (await client.get("/api/store/bizza")).json()
    assert body["name"] == "Bizza"
    assert len(body["menu"]) == 74
    assert (await client.get("/api/store/mc-racuchos")).status_code == 200


@pytest.mark.asyncio
async def test_login_and_tenant_isolation(Session, client, monkeypatch):
    await _seed(Session, monkeypatch, pins="bizza:clave4821,mc-racuchos:7310")
    ok = await client.post("/api/auth/login", json={"slug": "bizza", "pin": "clave4821"})
    assert ok.status_code == 200
    bad = await client.post("/api/auth/login", json={"slug": "bizza", "pin": "7310"})
    assert bad.status_code == 401
    h = {"X-Sabi-Token": ok.json()["token"]}
    assert (await client.get("/api/me", headers=h)).json()["slug"] == "bizza"
    menu = (await client.get("/api/menu", headers=h)).json()
    assert len(menu) == 74
    # an item of another restaurant is not reachable with Bizza's session
    async with Session() as s:
        other = (await s.execute(select(MenuItem).join(Restaurant).where(Restaurant.slug == "mc-racuchos"))).scalars().first()
    assert (await client.delete(f"/api/menu/{other.id}", headers=h)).status_code in (403, 404)


def test_greeting_detection():
    from app import concierge
    for ok in ("hola", "Hola!", "Buenas tardes", "¿Qué tienes?", "menú", "Hola Sabi"):
        assert concierge.is_greeting(ok), ok
    for no in ("hola quiero pizza", "quiero pastelitos", "Lechería", "me llamo Octavio"):
        assert not concierge.is_greeting(no), no


@pytest.mark.asyncio
async def test_hola_lists_every_business_even_with_an_open_conversation(Session, client, monkeypatch):
    from app.models import Conversation, Customer
    await _seed(Session, monkeypatch)
    async with Session() as s:
        mc = (await s.execute(select(Restaurant).where(Restaurant.slug == "mc-racuchos"))).scalar_one()
        cust = Customer(restaurant_id=mc.id, phone="584140000001", name="Octavio")
        s.add(cust)
        await s.flush()
        s.add(Conversation(customer_id=cust.id, status="open"))
        await s.commit()
    from app.routers.webhook import _resolve
    async with Session() as s:
        restaurant, _, reply = await _resolve(s, "584140000001", "hola")
        assert restaurant is None
        assert "Bizza" in reply and "MC Racuchos" in reply
        # the old conversation no longer captures the next message
        open_left = (await s.execute(select(func.count()).select_from(Conversation)
                                     .where(Conversation.status == "open"))).scalar_one()
        assert open_left == 0
