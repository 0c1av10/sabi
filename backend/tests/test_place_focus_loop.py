"""A catalog business never gets the unknown-place "¿Tienes un enlace oficial?" reply, and a
place focus that names one does not trap every follow-up in that reply (2026-11-23, Bizza)."""
from app.models import Restaurant, MenuItem
from app import conversation_focus as focus
from app.routers import webhook

ZONES = '[{"name": "Lechería", "fee": 2.0}, {"name": "Barcelona", "fee": 3.0}]'
LOOP = 'enlace oficial'


async def _seed(db):
    n = Restaurant(name='NACIONAL Restaurante', slug='nacional', pin='t', delivery_zones=ZONES)
    b = Restaurant(name='Bizza', slug='bizza', pin='t')
    db.add_all([n, b]); await db.flush()
    db.add_all([MenuItem(restaurant_id=b.id, name='Pizza Margarita', category='Pizzas', price=10),
                MenuItem(restaurant_id=n.id, name='Cachapa', category='Cachapas', price=12)])
    await db.commit()
    return n, b


async def test_stale_place_focus_on_catalog_business_does_not_loop(Session):
    async with Session() as db:
        _, b = await _seed(db)
        await focus.save(db, '111', domain='place', entity='Bizza también queda', city='lechería')
        for msg in ('Quiero una pizza margarita', 'Muéstrame el menú de Bizza'):
            restaurant, _, reply = await webhook._resolve(db, '111', msg)
            assert not (reply and LOOP in reply), (msg, reply)
        assert restaurant and restaurant.id == b.id


async def test_catalog_business_outside_its_zones_is_named_not_unknown(Session):
    async with Session() as db:
        await _seed(db)
        _, _, reply = await webhook._resolve(db, '111', 'NACIONAL Restaurante en Cumaná')
        assert 'no tiene delivery registrado en Cumaná' in reply
        assert 'Lechería y Barcelona' in reply
        assert LOOP not in reply and 'No lo tengo identificado' not in reply
        _, _, reply = await webhook._resolve(db, '111', 'Muéstrame el menú')
        assert not (reply and LOOP in reply)


async def test_unknown_place_keeps_asking_for_its_source(Session):
    async with Session() as db:
        await _seed(db)
        _, _, reply = await webhook._resolve(db, '111', 'De Beijing en lechería')
        assert 'No lo tengo identificado' in reply


async def test_city_change_with_catalog_business_states_its_coverage(Session):
    async with Session() as db:
        await _seed(db)
        await focus.save(db, '111', domain='restaurant', entity='NACIONAL Restaurante', city='Lechería')
        text = await webhook._events_route(db, '111', 'Mejor en Cumaná')
        assert 'no hace delivery a Cumaná' in text and 'Lechería y Barcelona' in text
        assert LOOP not in text
        await focus.save(db, '111', domain='restaurant', entity='Bizza', city='Lechería')
        text = await webhook._events_route(db, '111', 'Mejor en Cumaná')
        assert 'confirma si llega a Cumaná' in text and LOOP not in text
