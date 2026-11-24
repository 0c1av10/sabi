"""City listings include every visible business; unconfirmed coverage is clarified, never hidden or promised.

Decided 2026-11-23 (docs/CITY_LISTING.md): when a customer asks for food in a city, the
listing shows the businesses with registered delivery to that city AND the visible
businesses with no zones registered at all, clearly marked as coverage to confirm.
A business with zones registered for other cities stays out: its own data says where it
delivers. Ordering rules are unchanged: no business promises delivery to a city its own
data does not register.
"""
import pytest

from app.models import Restaurant

ZONES = '[{"name": "Lechería", "fee": 2.0}, {"name": "Barcelona", "fee": 3.0}]'


async def _seed(Session):
    async with Session() as s:
        s.add_all([
            Restaurant(name="NACIONAL Restaurante", slug="nacional", pin="1234", delivery_zones=ZONES),
            Restaurant(name="Bizza", slug="bizza", pin="1234"),
            Restaurant(name="MC Racuchos", slug="mc-racuchos", pin="1234"),
            Restaurant(name="La Esquina", slug="la-esquina", pin="1234"),
        ])
        await s.commit()


@pytest.mark.asyncio
async def test_city_listing_includes_zoneless_businesses(Session):
    from app.venezuela import local_options
    await _seed(Session)
    async with Session() as s:
        text = await local_options(s, "Lechería")
        assert "NACIONAL Restaurante" in text
        assert "Bizza" in text and "MC Racuchos" in text
        # Hidden businesses stay out even here.
        assert "Esquina" not in text
        # Unconfirmed businesses are clarified, never promised.
        assert "sin delivery a Lechería confirmado" in text
        assert text.index("te puedo atender") < text.index("sin delivery a Lechería confirmado")


@pytest.mark.asyncio
async def test_city_without_any_coverage_still_lists_zoneless(Session):
    from app.venezuela import local_options
    await _seed(Session)
    async with Session() as s:
        text = await local_options(s, "Puerto Ordaz")
        assert "no tengo locales con delivery confirmado" in text
        assert "Bizza" in text and "MC Racuchos" in text
        # NACIONAL has zones registered elsewhere: its own data says it does not cover.
        assert "NACIONAL" not in text


@pytest.mark.asyncio
async def test_covers_does_not_promise_zoneless_business(Session):
    from app.venezuela import covers
    from sqlalchemy import select
    await _seed(Session)
    async with Session() as s:
        bizza = (await s.execute(select(Restaurant).where(Restaurant.slug == "bizza"))).scalar_one()
        nacional = (await s.execute(select(Restaurant).where(Restaurant.slug == "nacional"))).scalar_one()
        assert await covers(s, bizza, "Lechería") is False
        assert await covers(s, nacional, "Lechería") is True


@pytest.mark.asyncio
async def test_fees_appear_only_for_registered_zones(Session):
    from app.venezuela import local_options
    await _seed(Session)
    async with Session() as s:
        text = await local_options(s, "Lechería", fees=True)
        assert "delivery a Lechería" in text  # NACIONAL's registered zone line
        unsure = text.split("sin delivery a Lechería confirmado", 1)[1]
        assert "$" not in unsure  # no invented fee for unconfirmed businesses


@pytest.mark.asyncio
async def test_zoneless_catalog_business_is_recognized_not_unresolved(Session):
    """Production evidence 2026-11-23: "Bizza también queda en lechería" got the
    official-link ask although Bizza is in the catalog. A visible business with no
    zones registered is identified: route to it, coverage confirmed at order time."""
    from app.routers.webhook import _unresolved_place_reply
    await _seed(Session)
    async with Session() as s:
        assert await _unresolved_place_reply(s, "584120000001", "Bizza también queda en lechería") is None
        # A covered catalog business was and stays resolved.
        assert await _unresolved_place_reply(s, "584120000003", "¿Conoces NACIONAL en Lechería?") is None
        # A hidden demo business is not in the visible catalog: still an unresolved place.
        reply = await _unresolved_place_reply(s, "584120000002", "¿Conoces el restaurante La Esquina?")
        assert reply is not None and "enlace oficial" in reply
