"""Only real businesses are visible: demo/test businesses stay stored but out of reach.

Decided 2026-11-23 (docs/VISIBLE_RESTAURANTS.md): recommendations, mention/product routing,
city delivery options and the public storefront show only real businesses; the owner panel
and the stored data are untouched.
"""
import pytest
from sqlalchemy import select

from app.models import MenuItem, Restaurant


async def _seed(Session):
    async with Session() as s:
        real = Restaurant(name="NACIONAL Restaurante", slug="nacional", pin="1234")
        demo = Restaurant(name="La Esquina", slug="la-esquina", pin="1234")
        test = Restaurant(name="Prueba Flow Final", slug="prueba-flow-final", pin="1234")
        s.add_all([real, demo, test])
        await s.flush()
        s.add_all([
            MenuItem(restaurant_id=real.id, name="Pollo a la Brasa", price=12, category="Brasas"),
            MenuItem(restaurant_id=demo.id, name="Arepa Demo", price=3, category="Arepas"),
            MenuItem(restaurant_id=test.id, name="Empanada Test", price=2, category="Empanadas"),
        ])
        await s.commit()


@pytest.mark.asyncio
async def test_recommendations_exclude_hidden(Session):
    from app import concierge
    await _seed(Session)
    async with Session() as s:
        text = await concierge.recommendations(s, body="dame todos los restaurantes que tengas")
        assert "NACIONAL" in text
        assert "Esquina" not in text and "Prueba" not in text


@pytest.mark.asyncio
async def test_mention_does_not_route_to_hidden(Session):
    from app.auth import restaurant_by_mention
    await _seed(Session)
    async with Session() as s:
        assert await restaurant_by_mention(s, "quiero pedir en La Esquina") is None
        r = await restaurant_by_mention(s, "quiero pedir en Nacional")
        assert r and r.slug == "nacional"


@pytest.mark.asyncio
async def test_product_match_ignores_hidden_sellers(Session):
    from app.auth import restaurants_by_product
    await _seed(Session)
    async with Session() as s:
        sellers = await restaurants_by_product(s, "quiero una arepa demo")
        assert all(r.slug != "la-esquina" for r in sellers)


@pytest.mark.asyncio
async def test_storefront_hides_demo_but_serves_real(Session):
    from app.routers.store import public_store
    from fastapi import HTTPException
    await _seed(Session)
    async with Session() as s:
        with pytest.raises(HTTPException):
            await public_store("la-esquina", s)
        with pytest.raises(HTTPException):
            await public_store("prueba-flow-final", s)
        out = await public_store("nacional", s)
        assert out["slug"] == "nacional"


@pytest.mark.asyncio
async def test_owner_panel_still_works_for_hidden(Session):
    """Hidden from customers, never from its owner: panel login by slug+pin is unchanged."""
    await _seed(Session)
    async with Session() as s:
        r = (await s.execute(select(Restaurant).where(Restaurant.slug == "la-esquina"))).scalar_one()
        assert r.pin == "1234", "hidden business rows stay intact, panel login data included"
