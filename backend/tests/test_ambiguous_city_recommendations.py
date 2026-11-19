from datetime import timedelta
from app import concierge,conversation_focus as focus,memory,cinema_whatsapp as cinema
from app.models import utcnow
from app.routers import webhook

async def test_ambiguous_city_after_greeting_asks_domain_without_catalog(Session,monkeypatch):
    sent=[]
    async def send(phone,text):sent.append(text);return {'mock':True}
    async def forbidden(*args,**kwargs):raise AssertionError('no catalog or live lookup allowed')
    monkeypatch.setattr(webhook,'send_whatsapp_message',send)
    monkeypatch.setattr(concierge,'recommendations',forbidden)
    async with Session() as db:
        await memory.note(db,'111',topic='cine')
        # Old cinema context is expired, even though the long-term last topic is cine.
        await focus.save(db,'111',domain='cinema',city='Puerto La Cruz',now=utcnow()-timedelta(hours=4))
        await webhook._resolve(db,'111','Hola')
        reply=await webhook._events_route(db,'111','En lechería que me recomiendas')
        assert reply=='¿Buscas comida o un plan de cine en Lechería?'
        assert (await focus.get(db,'111')).city=='Lechería'
        reply=await webhook._events_route(db,'111','comida')
        assert 'filtro geográfico' in reply and 'Lechería' in reply
        assert '¿Buscas comida' not in reply
        assert await focus.get(db,'222') is None

async def test_recent_cinema_localized_recommendation_uses_city(Session,monkeypatch):
    queries=[]
    async def send(*args):return {'mock':True}
    async def run(body,**kw):queries.append(body);return 'Respuesta simulada de cine, no cartelera real.'
    monkeypatch.setattr(webhook,'send_whatsapp_message',send)
    monkeypatch.setattr(cinema,'send_whatsapp_message',send)
    monkeypatch.setattr(cinema,'run_cinema_agent',run)
    monkeypatch.setattr(cinema.settings,'cinema_mcp_enabled',True)
    async with Session() as db:
        await focus.save(db,'111',domain='cinema',city='Puerto La Cruz')
        assert 'simulada' in await webhook._events_route(db,'111','En lechería que me recomiendas')
        assert 'Ciudad explícita para esta consulta: Lechería.' in queries[0]
        assert (await focus.get(db,'111')).city=='Lechería'

async def test_cinema_answer_after_domain_clarification_preserves_city(Session,monkeypatch):
    called=[]
    async def send(*args):return {'mock':True}
    async def wants(*args):return True
    async def handle(db,phone,body,*args):called.append((await focus.get(db,phone)).city);return 'cine simulado'
    monkeypatch.setattr(webhook,'send_whatsapp_message',send)
    monkeypatch.setattr(webhook,'wants_cinema',wants)
    monkeypatch.setattr(webhook,'handle_cinema_whatsapp',handle)
    async with Session() as db:
        await webhook._events_route(db,'111','En Valencia que me recomiendas')
        assert await webhook._events_route(db,'111','cine')=='cine simulado'
        assert called==['Valencia']

async def test_generic_recommendation_no_longer_means_food(Session):
    async with Session() as db:
        assert not concierge.wants_food('Qué me recomiendas')
        text,_=await concierge.reply(db,'Qué me recomiendas','111')
        assert text=='¿Buscas comida o un plan de cine?'
        assert concierge.wants_food('Recomiéndame una pizza')
        assert not concierge.ambiguous_recommendation('Recomiéndame comida china')

async def test_invalid_saved_name_not_used_in_food_and_not_mutated(Session,monkeypatch):
    async def recommendations(*args,**kwargs):return 'Opciones simuladas.'
    monkeypatch.setattr(concierge,'recommendations',recommendations)
    async with Session() as db:
        db.add(memory.Contact(phone='111',name='Entonces',last_topic='cine'));await db.commit()
        text,_=await concierge.reply(db,'Quiero comida','111')
        assert text=='Opciones simuladas.' and 'Entonces' not in text and 'rico' not in text
        assert (await memory.get(db,'111')).name=='Entonces'

import pytest

@pytest.mark.parametrize('body', ['En Lechería, ¿qué me recomiendas?','Qué me recomiendas en Lechería?','Recomiéndame algo en Lechería','En Lechería recomiéndame algo'])
async def test_natural_variants_do_not_choose_food(Session,monkeypatch,body):
    async def send(*args):return {'mock':True}
    monkeypatch.setattr(webhook,'send_whatsapp_message',send)
    async with Session() as db:
        reply=await webhook._events_route(db,'111',body)
        assert reply=='¿Buscas comida o un plan de cine en Lechería?'

@pytest.mark.parametrize('body',['No quiero cine, quiero comida en Valencia','No comida, recomiéndame cine en Valencia','Ni cine ni comida'])
async def test_negations_clarify_without_any_catalog_or_cinema(Session,monkeypatch,body):
    async def send(*args):return {'mock':True}
    async def forbidden(*args,**kwargs):raise AssertionError('do not select a negated domain')
    monkeypatch.setattr(webhook,'send_whatsapp_message',send)
    monkeypatch.setattr(webhook,'handle_cinema_whatsapp',forbidden)
    monkeypatch.setattr(concierge,'recommendations',forbidden)
    async with Session() as db:
        await focus.save(db,'111',domain='cinema',city='Lechería')
        assert '¿Quieres seguir con cine' in await webhook._events_route(db,'111',body)

async def test_explicit_food_switch_cannot_use_stale_city(Session,monkeypatch):
    async def send(*args):return {'mock':True}
    monkeypatch.setattr(webhook,'send_whatsapp_message',send)
    async with Session() as db:
        await focus.save(db,'111',domain='cinema',city='Lechería')
        reply=await webhook._events_route(db,'111','Quiero comida en Valencia')
        assert 'Valencia' in reply and 'filtro geográfico' in reply and 'Lechería' not in reply
        assert (await focus.get(db,'111')).city=='Valencia'

async def test_localized_food_direct_catalog_never_randomizes_city(Session,monkeypatch):
    from app.models import Restaurant
    async with Session() as db:
        db.add(Restaurant(name='Local simulado ajeno',slug='fake',pin='test',tagline='Restaurante en Caracas'));await db.commit()
        text=await concierge.recommendations(db,body='Quiero comida en Valencia')
        assert 'Valencia' in text and 'filtro geográfico' in text and 'ajeno' not in text and 'Caracas' not in text
        generic=await concierge.recommendations(db,body='Quiero comida')
        assert 'sin confirmar su ubicación' in generic and 'Restaurante en Caracas' not in generic

@pytest.mark.parametrize('name,expected',[('Entonces',''),('Ahora',''),('Ana','Ana'),('Octavio Caamano','Octavio')])
def test_shared_first_name_filters_all_callers(name,expected):assert memory.display_name(name)==expected

async def test_explicit_food_without_new_city_can_leave_cinema(Session,monkeypatch):
    async def no(*args,**kwargs):return False
    monkeypatch.setattr(webhook.gym_whatsapp,'wants_gym',no)
    monkeypatch.setattr(webhook,'wants_events',no)
    async with Session() as db:
        await focus.save(db,'111',domain='cinema',city='Lechería')
        assert await webhook._events_route(db,'111','Quiero pizza') is None
        assert not await cinema.wants_cinema(db,'111','Quiero pizza')

async def test_pending_city_does_not_lock_named_place(Session,monkeypatch):
    sent=[]
    async def send(phone,text):sent.append(text);return {'mock':True}
    monkeypatch.setattr(webhook,'send_whatsapp_message',send)
    async with Session() as db:
        await webhook._events_route(db,'111','Qué me recomiendas en Valencia')
        text=await webhook._events_route(db,'111','Conoces LocalDePrueba')
        assert 'LocalDePrueba' in text and '¿Buscas comida' not in text

async def test_pending_city_does_not_block_unrelated_work(Session,monkeypatch):
    async def send(*args):return {'mock':True}
    async def no(*args,**kwargs):return False
    monkeypatch.setattr(webhook,'send_whatsapp_message',send)
    monkeypatch.setattr(webhook.gym_whatsapp,'wants_gym',no)
    monkeypatch.setattr(webhook,'wants_events',no)
    async with Session() as db:
        await webhook._events_route(db,'111','Qué me recomiendas en Valencia')
        assert await webhook._events_route(db,'111','Ayúdame con un trabajo') is None
