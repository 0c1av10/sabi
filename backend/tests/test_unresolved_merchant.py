from datetime import timedelta
import json
from sqlalchemy import select
from app.models import Restaurant,MenuItem,Customer,Conversation,Order,utcnow
from app import conversation_focus as focus
from app.auth import restaurant_for_message,restaurants_by_product,named_business_query
from app.routers import webhook

async def catalog(db,opened=False):
    n=Restaurant(name='NACIONAL Restaurante',slug='nacional',pin='test',tagline='Cocina criolla')
    b=Restaurant(name='Bizza',slug='bizza',pin='test')
    db.add_all([n,b]);await db.flush()
    db.add_all([MenuItem(restaurant_id=n.id,name='Cachapa Lechería',category='Cachapas',price=12),MenuItem(restaurant_id=b.id,name='Pizza Margarita',category='Pizzas',price=10)])
    if opened:
        c=Customer(restaurant_id=n.id,phone='111',name='Ana');db.add(c);await db.flush()
        db.add(Conversation(restaurant_id=n.id,customer_id=c.id,status='open',state_json=json.dumps({'items':[{'name':'old item'}],'delivery_zone':'Lechería'})))
    await db.commit();return n,b

async def test_city_only_suffix_never_selects_nacional(Session):
    async with Session() as db:
        await catalog(db)
        assert not await restaurants_by_product(db,'De Beijing en lechería')
        assert (await restaurant_for_message(db,'111','De Beijing en lechería'))[0] is None
        assert (await restaurant_for_message(db,'111','quiero pizza'))[0].slug=='bizza'

async def test_unknown_named_business_blocks_existing_tenant_without_erasing_order(Session,monkeypatch):
    sent=[]
    async def send(phone,text):sent.append(text);return True
    monkeypatch.setattr(webhook,'send_whatsapp_message',send)
    async with Session() as db:
        n,b=await catalog(db,True)
        await focus.save(db,'111',domain='restaurant',entity=n.name)
        old=(await db.execute(select(Conversation))).scalar_one();old_id=old.id;state=old.state_json
        text=await webhook._events_route(db,'111','De Beijing en lechería')
        assert 'Beijing' in text and 'lechería' in text and 'no voy a usar' in text
        assert 'Cachapa' not in text and '$2' not in text and sent==[text]
        assert (await focus.get(db,'111')).domain=='place'
        assert (await restaurant_for_message(db,'111','¿Y el horario?'))[0] is None
        await db.refresh(old)
        assert old.id==old_id and old.status=='open' and old.state_json==state
        assert not (await db.execute(select(Order))).scalars().all()

async def test_full_greeting_then_unknown_entity_resolves_without_model(Session,monkeypatch):
    async def send(*a,**k):return True
    async def forbidden(*a,**k):raise AssertionError('No model, shopping or live outbound in router replay')
    monkeypatch.setattr(webhook,'send_whatsapp_message',send)
    monkeypatch.setattr(webhook,'handle_cinema_whatsapp',forbidden)
    async with Session() as db:
        await catalog(db,True)
        assert await webhook._events_route(db,'111','Hola') is None
        assert (await webhook._resolve(db,'111','Hola'))[0] is None
        text=await webhook._events_route(db,'111','De Beijing en lechería')
        assert text and (await webhook._resolve(db,'111','¿Tienes el menú?'))[0] is None

async def test_previous_tenant_survives_focus_expiry_but_not_other_domains(Session):
    async with Session() as db:
        n,_=await catalog(db,True)
        # An open conversation keeps its restaurant even with no active focus (2026-11-20
        # continuity fix: an order follow-up must not fall back to the welcome after 30 min).
        assert (await restaurant_for_message(db,'111','¿Tienen delivery?'))[0].id==n.id
        await focus.save(db,'111',domain='restaurant',entity=n.name)
        assert (await restaurant_for_message(db,'111','¿Tienen delivery?'))[0].id==n.id
        await focus.save(db,'111',domain='cinema')
        assert (await restaurant_for_message(db,'111','¿Tienen delivery?'))[0] is None
        await focus.save(db,'111',domain='restaurant',entity=n.name,now=utcnow()-timedelta(minutes=31))
        # Old write protection leaves cinema, still cannot restore restaurant.
        assert (await restaurant_for_message(db,'111','¿Tienen delivery?'))[0] is None

async def test_known_merchant_and_tag_keep_valid_routes(Session):
    async with Session() as db:
        await catalog(db)
        for text in ('De Bizza en lechería','Quiero pedir en Bizza','[sabi:bizza] hola'):
            assert (await restaurant_for_message(db,'111',text))[0].slug=='bizza'
        for text in ('Quiero pedir en Abruzzos','Sobre Acme en Valencia','Qué sabes del restaurante Epsilon'):
            assert named_business_query(text) is not None
            assert (await restaurant_for_message(db,'111',text))[0] is None
