"""Requests for businesses outside the catalog land on a review list (docs/REQUESTED_BUSINESSES.md).

The list holds only the business name and the city when the customer stated it;
repeat asks raise a counter instead of duplicating rows, and nothing here
auto-onboards a business.
"""
import pytest
from sqlalchemy import select

from app.models import RequestedBusiness


@pytest.mark.asyncio
async def test_record_creates_one_row(Session):
    from app import requested
    async with Session() as s:
        await requested.record(s, "Pizzería Roma", "Lechería")
        rows = (await s.execute(select(RequestedBusiness))).scalars().all()
        assert len(rows) == 1
        assert rows[0].name == "Pizzería Roma"
        assert rows[0].city == "Lechería"
        assert rows[0].requests == 1


@pytest.mark.asyncio
async def test_repeat_ask_counts_without_duplicating(Session):
    from app import requested
    async with Session() as s:
        await requested.record(s, "Pizzería Roma", "")
        await requested.record(s, "pizzeria  roma", "")
        rows = (await s.execute(select(RequestedBusiness))).scalars().all()
        assert len(rows) == 1
        assert rows[0].requests == 2
        assert rows[0].first_requested_at <= rows[0].last_requested_at


@pytest.mark.asyncio
async def test_later_city_fills_empty_one(Session):
    from app import requested
    async with Session() as s:
        await requested.record(s, "Sushi Go", "")
        await requested.record(s, "Sushi Go", "Puerto La Cruz")
        row = (await s.execute(select(RequestedBusiness))).scalar_one()
        assert row.city == "Puerto La Cruz"
        # A stored city is never replaced by a different one or a blank.
        await requested.record(s, "Sushi Go", "Caracas")
        await requested.record(s, "Sushi Go", "")
        assert (await s.execute(select(RequestedBusiness))).scalar_one().city == "Puerto La Cruz"


@pytest.mark.asyncio
async def test_unresolved_place_message_is_recorded(Session):
    from app.routers.webhook import _unresolved_place_reply
    async with Session() as s:
        reply = await _unresolved_place_reply(s, "584120000001", "¿Conoces el restaurante El Fogón Andino en Mérida?")
        assert "El Fogón Andino" in reply
        row = (await s.execute(select(RequestedBusiness))).scalar_one()
        assert row.name_key == "el fogon andino"
        assert row.city == "Mérida"


@pytest.mark.asyncio
async def test_catalog_business_is_not_recorded(Session):
    from app.models import Restaurant
    from app.routers.webhook import _unresolved_place_reply
    async with Session() as s:
        s.add(Restaurant(name="NACIONAL Restaurante", slug="nacional", pin="1234"))
        await s.commit()
        reply = await _unresolved_place_reply(s, "584120000001", "¿Conoces el restaurante NACIONAL?")
        assert reply is None
        rows = (await s.execute(select(RequestedBusiness))).scalars().all()
        assert rows == []
