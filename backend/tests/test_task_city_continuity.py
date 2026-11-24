from app import conversation_focus as focus
from app.routers import webhook
from app.models import Restaurant,Customer,Conversation

async def test_same_restaurant_keeps_explicit_city(Session):
    async with Session() as db:
        r=Restaurant(name='Bizza',slug='bizza',pin='test');db.add(r);await db.flush()
        c=Customer(restaurant_id=r.id,phone='111');db.add(c);await db.flush()
        db.add(Conversation(restaurant_id=r.id,customer_id=c.id,status='open'));await db.commit()
        await focus.save(db,'111',domain='restaurant',entity='Bizza',city='Lechería')
        restaurant,_,reply=await webhook._resolve(db,'111','Mándamelo en tres mensajes')
        assert restaurant.id==r.id and reply is None
        assert (await focus.get(db,'111')).city=='Lechería'

async def test_repeat_same_place_does_not_ask_city_again(Session):
    async with Session() as db:
        await focus.save(db,'111',domain='place',entity='Acme',city='Valencia')
        text=await focus.place_reply(db,'111','Conoces Acme')
        assert 'Valencia' in text and '¿En qué ciudad' not in text
        assert (await focus.get(db,'111')).city=='Valencia'
        text=await focus.place_reply(db,'111','Conoces Otro')
        assert '¿En qué ciudad' in text
        assert (await focus.get(db,'111')).city==''
        assert await focus.get(db,'222') is None

async def test_different_restaurant_does_not_inherit_city(Session):
    async with Session() as db:
        r=Restaurant(name='Bizza',slug='bizza',pin='test');db.add(r);await db.commit()
        await focus.save(db,'111',domain='place',entity='Acme',city='Valencia')
        restaurant,_,reply=await webhook._resolve(db,'111','Quiero pedir en Bizza')
        assert restaurant.id==r.id
        assert (await focus.get(db,'111')).city==''

async def test_city_change_keeps_entity_but_rejects_old_catalog(Session,monkeypatch):
    sent=[]
    async def send(phone,text):sent.append(text);return {'mock':True}
    monkeypatch.setattr(webhook,'send_whatsapp_message',send)
    async with Session() as db:
        r=Restaurant(name='Bizza',slug='bizza',pin='test');db.add(r);await db.flush()
        c=Customer(restaurant_id=r.id,phone='111');db.add(c);await db.flush()
        db.add(Conversation(restaurant_id=r.id,customer_id=c.id,status='open'));await db.commit()
        await focus.save(db,'111',domain='restaurant',entity='Bizza',city='Lechería')
        text=await webhook._events_route(db,'111','Mejor en Valencia')
        # Bizza registered no zones: coverage is confirmed by the local, never asked as a link (docs/CITY_LISTING.md).
        assert 'Valencia' in text and 'confirma si llega a Valencia' in text and 'enlace' not in text
        a=await focus.get(db,'111');assert (a.domain,a.entity,a.city)==('restaurant','Bizza','Valencia')
        rest,_,reply=await webhook._resolve(db,'111','Y cuál es la mejor')
        assert rest and rest.name=='Bizza' and reply is None
        assert await focus.get(db,'222') is None

async def test_explicit_city_first_then_place_preserves_declared_query_city(Session):
    async with Session() as db:
        text=await focus.city_reply(db,'111','Estoy en Valencia')
        assert 'Valencia' in text
        text=await webhook._unresolved_place_reply(db,'111','De Acme')
        assert 'Valencia' in text
        assert (await focus.get(db,'111')).city=='Valencia'

async def test_format_is_not_city_and_city_is_updated(Session):
    async with Session() as db:
        await focus.save(db,'111',domain='place',entity='Acme',city='Valencia')
        assert await focus.city_reply(db,'111','Mándamelo en tres mensajes') is None
        assert (await focus.get(db,'111')).city=='Valencia'
        assert 'Valencia' in await focus.city_reply(db,'111','En Valencia')
        assert 'ahora' in await focus.city_reply(db,'111','Ahora en Caracas')
        assert (await focus.get(db,'111')).city=='Caracas'

async def test_other_domains_store_city_without_fake_geo_search(Session):
    async with Session() as db:
        await focus.save(db,'111',domain='shopping',entity='laptop Dell',platform='Yummy Marketplace')
        text=await focus.city_reply(db,'111','Estoy en Valencia')
        assert 'no tiene un filtro geográfico verificado' in text
        a=await focus.get(db,'111');assert a.entity=='laptop Dell' and a.city=='Valencia' and a.platform=='Yummy Marketplace'

async def test_cuisine_followup_does_not_escape_city_guard(Session):
    async with Session() as db:
        await focus.save(db,'111',domain='place',entity='Bizza',city='Valencia')
        rest,_,reply=await webhook._resolve(db,'111','Quiero pizza')
        assert rest is None and 'Valencia' in reply and 'otra ciudad' in reply

async def test_known_name_with_new_city_never_uses_old_catalog(Session):
    async with Session() as db:
        r=Restaurant(name='Bizza',slug='bizza',pin='test');db.add(r);await db.commit()
        await focus.save(db,'111',domain='restaurant',entity='Bizza',city='Lechería')
        rest,_,reply=await webhook._resolve(db,'111','De Bizza en Valencia')
        # Bizza has no zones registered: it is identified and routes (no official-link ask),
        # but the stated new city is never replaced by the old task city (docs/CITY_LISTING.md).
        assert rest is not None and rest.slug=='bizza' and reply is None
        assert (await focus.get(db,'111')).city==''
