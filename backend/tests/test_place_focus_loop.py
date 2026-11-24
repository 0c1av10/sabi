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


async def _open_order(db, restaurant, state):
    import json
    from app.models import Customer, Conversation
    c = Customer(restaurant_id=restaurant.id, phone='111'); db.add(c); await db.flush()
    conv = Conversation(restaurant_id=restaurant.id, customer_id=c.id, state_json=json.dumps(state))
    db.add(conv); await db.commit()
    return conv


async def test_city_change_drops_the_old_address_of_an_open_order(Session):
    import json
    async with Session() as db:
        n, _ = await _seed(db)
        conv = await _open_order(db, n, {'stage': 'payment', 'draft': {
            'items': [{'name': 'Cachapa', 'quantity': 1}], 'order_type': 'delivery',
            'address': 'Av. Principal, Lechería', 'delivery_zone': 'Lechería'}})
        await focus.save(db, '111', domain='restaurant', entity='NACIONAL Restaurante', city='Lechería')
        text = await webhook._events_route(db, '111', 'Mejor en Barcelona')
        assert 'Barcelona' in text
        await db.refresh(conv)
        state = json.loads(conv.state_json)
        assert state['stage'] == 'chat' and not state['draft']['address'] and state['draft']['items']


async def test_menu_after_naming_another_business_is_from_that_business(Session):
    async with Session() as db:
        n, b = await _seed(db)
        await _open_order(db, b, {})
        await webhook._resolve(db, '111', 'NACIONAL Restaurante en Cumaná')
        restaurant, _, _ = await webhook._resolve(db, '111', 'Muéstrame el menú')
        assert restaurant and restaurant.id == n.id


async def test_full_catalog_ask_is_not_sent_to_the_focused_business(Session):
    async with Session() as db:
        await _seed(db)
        await focus.save(db, '111', domain='place', entity='Bizza también queda', city='lechería')
        restaurant, _, reply = await webhook._resolve(db, '111', 'Dame todos los restaurantes que tengas')
        assert restaurant is None and reply and 'NACIONAL' in reply


async def test_first_stated_city_keeps_the_order_address(Session):
    import json
    async with Session() as db:
        n, _ = await _seed(db)
        conv = await _open_order(db, n, {'stage': 'payment', 'draft': {
            'items': [{'name': 'Cachapa', 'quantity': 1}], 'order_type': 'delivery',
            'address': 'Av. Principal, Lechería', 'delivery_zone': 'Lechería'}})
        await focus.save(db, '111', domain='restaurant', entity='NACIONAL Restaurante')
        await webhook._events_route(db, '111', 'Es en Lechería')
        await db.refresh(conv)
        state = json.loads(conv.state_json)
        assert state['stage'] == 'payment' and state['draft']['address']


async def test_product_only_one_business_sells_ignores_an_earlier_query(Session):
    async with Session() as db:
        n, b = await _seed(db)
        await _open_order(db, b, {})
        await focus.save(db, '111', domain='restaurant', entity='NACIONAL Restaurante')
        restaurant, _, _ = await webhook._resolve(db, '111', 'Quiero una Pizza Margarita')
        assert restaurant and restaurant.id == b.id
        await focus.save(db, '112', domain='restaurant', entity='NACIONAL Restaurante')
        restaurant, _, _ = await webhook._resolve(db, '112', 'Quiero una Pizza Margarita')
        assert restaurant and restaurant.id == b.id


async def test_menu_of_the_business_just_named_needs_no_switch_confirmation(Session):
    from app import memory
    async with Session() as db:
        n, b = await _seed(db)
        await _open_order(db, b, {})
        await memory.set_topic(db, '111', 'tu pedido en Bizza')
        await webhook._resolve(db, '111', 'NACIONAL Restaurante en Cumaná')
        restaurant, _, reply = await webhook._resolve(db, '111', 'Muéstrame el menú')
        assert restaurant and restaurant.id == n.id and not reply
