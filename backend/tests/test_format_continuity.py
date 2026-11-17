import json
from pathlib import Path
import pytest
from sqlalchemy import select
from app import conversation_focus as focus,memory
from app.auth import named_business_query,response_format_request
from app.models import Restaurant,MenuItem,Customer,Conversation,Order
from app.routers import webhook

@pytest.mark.parametrize('text',[
    'Mándamelo en tres mensajes','Mandamelo en 3 mensajes','Envíamelo en dos partes',
    'Pásamelo en una tabla','Dímelo en pocas palabras','Resúmelo en tres líneas',
    'Divídelo en tres mensajes','Por favor mándamelo en mensajes cortos',
    'Puedes enviarlo en tres mensajes','Mándame el menú en tres mensajes',
])
def test_format_not_merchant(text):
    assert response_format_request(text)
    assert named_business_query(text) is None

@pytest.mark.parametrize('text,entity',[
    ('De Beijing en lechería','Beijing'),('Sobre Acme en Valencia','Acme'),
    ('Del restaurante Mensajes en Valencia','Mensajes'),
    ('Quiero pedir en Beijing en Lechería','Beijing'),
])
def test_real_places_still_guarded(text,entity):assert named_business_query(text)[0]==entity

async def test_full_pizza_format_recommendation_continuity(Session,monkeypatch):
    sent=[]
    async def send(phone,text):sent.append(text);return {'mock':True}
    async def forbidden(*a,**k):raise AssertionError('No live model, network or cinema allowed')
    monkeypatch.setattr(webhook,'send_whatsapp_message',send)
    monkeypatch.setattr(webhook,'handle_cinema_whatsapp',forbidden)
    evidence=[]
    async with Session() as db:
        b=Restaurant(name='Bizza',slug='bizza',pin='test');n=Restaurant(name='NACIONAL Restaurante',slug='nacional',pin='test')
        db.add_all([b,n]);await db.flush()
        db.add_all([MenuItem(restaurant_id=b.id,name='Pizza Margarita',category='Pizzas',price=10),MenuItem(restaurant_id=n.id,name='Cachapa Lechería',category='Cachapas',price=12)])
        c=Customer(restaurant_id=b.id,phone='111',name='Persona de prueba');db.add(c);await db.flush()
        conv=Conversation(restaurant_id=b.id,customer_id=c.id,status='open',state_json=json.dumps({'items':[],'last_category':'Pizzas'}));db.add(conv);await db.commit()
        state=conv.state_json
        await memory.note(db,'111','Me llamo Ana')
        # Current first step routes to the only verified pizza seller.
        for body in ['Del restaurante pizza','Mándamelo en tres mensajes','Y cual es la mejor']:
            early=await webhook._events_route(db,'111',body)
            assert early is None
            rest,routed,reply=await webhook._resolve(db,'111',body)
            assert rest and rest.id==b.id and routed==body and reply is None
            active=await focus.get(db,'111')
            assert active.domain=='restaurant' and active.entity=='Bizza'
            evidence.append({'input':body,'merchant':rest.name,'forwarded_unchanged':routed,'focus':active.entity,'premature_reply':reply})
        assert sent==[]
        await db.refresh(conv);assert conv.state_json==state and conv.status=='open'
        assert not (await db.execute(select(Order))).scalars().all()
        assert await focus.get(db,'222') is None
    Path('/downloads/sabi-format-sequence-evidence.json').write_text(json.dumps({'type':'isolated router replay, model and transport blocked','steps':evidence,'limit':'The restaurant response generator receives the formatting instruction unchanged. This does not prove three outbound messages, complete menu content, recommendation prose or WhatsApp delivery.'},ensure_ascii=False,indent=2))

async def test_format_without_context_does_not_invent_restaurant(Session):
    async with Session() as db:
        assert await webhook._unresolved_place_reply(db,'111','Mándamelo en tres mensajes') is None
        assert await focus.get(db,'111') is None

async def test_format_cannot_switch_unknown_place_back_to_old_catalog(Session,monkeypatch):
    async def send(*a,**k):return {'mock':True}
    monkeypatch.setattr(webhook,'send_whatsapp_message',send)
    async with Session() as db:
        n=Restaurant(name='NACIONAL Restaurante',slug='nacional',pin='test');db.add(n);await db.flush()
        c=Customer(restaurant_id=n.id,phone='111');db.add(c);await db.flush()
        db.add(Conversation(restaurant_id=n.id,customer_id=c.id,status='open'));await db.commit()
        await focus.save(db,'111',domain='place',entity='Beijing',city='Lechería')
        rest,_,reply=await webhook._resolve(db,'111','Mándamelo en tres mensajes')
        assert rest is None and 'Beijing' in reply
        assert (await focus.get(db,'111')).entity=='Beijing'

@pytest.mark.parametrize('text',[
    'Uno\n\nDos\n\nTres',
    'Encabezado\nPizza 1 $10\nPizza 2 $12\nPizza 3 $14\nFuente: https://example.test/producto/123',
    'Este texto tiene palabras suficientes para partirlo sin perder ni duplicar contenido.',
])
def test_split_content_preserved(text):
    from app.response_format import split_reply
    parts=split_reply(text,3)
    assert len(parts)==3 and all(parts)
    assert ' '.join(' '.join(parts).split())==' '.join(text.split())
    assert ''.join(parts).count('https://')==text.count('https://')

async def test_three_sequential_transport_calls_no_model_or_order(Session,monkeypatch):
    from app import service
    from app.agent import AgentResult
    from app.response_format import requested_parts
    assert requested_parts('Mándamelo en tres mensajes')==3
    assert requested_parts('Restaurante Tres Mensajes en Valencia') is None
    sends=[];calls=[]
    source='Pizza A: $10\n\nPizza B: $12\n\nPizza C: $14'
    async def agent(db,rest,conv,history,body):
        calls.append(body)
        return AgentResult(reply=source,state={'items':[]})
    async def rates(*a):return None
    async def send(phone,text):sends.append({'phone':phone,'body':text});return {'mock':True}
    monkeypatch.setattr(service,'run_agent',agent)
    monkeypatch.setattr(service,'refresh_rates',rates)
    monkeypatch.setattr(service,'send_whatsapp_message',send)
    async with Session() as db:
        r=Restaurant(name='Bizza',slug='bizza',pin='test');db.add(r);await db.commit()
        answer=await service.handle_inbound_message(db,r,'111','Mándamelo en tres mensajes',external_id='isolated-format-1')
        assert answer==source and calls==['Mándamelo en tres mensajes']
        assert len(sends)==3 and all(s['phone']=='111' for s in sends)
        assert '\n\n'.join(s['body'] for s in sends)==source
        await service.handle_inbound_message(db,r,'111','Mándamelo en tres mensajes',external_id='isolated-format-1')
        assert len(sends)==3 and len(calls)==1
        assert not (await db.execute(select(Order))).scalars().all()
    Path('/downloads/sabi-format-three-sends-evidence.json').write_text(json.dumps({'type':'isolated service test: generated reply fixed, transport recording fake','input':calls[0],'logical_reply':source,'recorded_transport_calls':sends,'retry_same_inbound_total_calls':len(sends),'limit':'No live model, real catalog, WhatsApp delivery or complete-menu generation proved.'},ensure_ascii=False,indent=2))

async def test_transport_failure_stops_without_resend(Session,monkeypatch):
    from app import service
    from app.agent import AgentResult
    sent=[]
    async def rates(*a):return None
    async def agent(*a):return AgentResult(reply='Primera\n\nSegunda\n\nTercera')
    async def send(phone,text):
        sent.append(text)
        if len(sent)==2:raise TimeoutError('isolated transport failure')
        return {'mock':True}
    monkeypatch.setattr(service,'refresh_rates',rates)
    monkeypatch.setattr(service,'run_agent',agent)
    monkeypatch.setattr(service,'send_whatsapp_message',send)
    async with Session() as db:
        r=Restaurant(name='Bizza',slug='bizza',pin='test');db.add(r);await db.commit()
        with pytest.raises(TimeoutError):await service.handle_inbound_message(db,r,'111','Mándamelo en tres mensajes',external_id='isolated-failure')
        assert sent==['Primera','Segunda']
        assert await service.handle_inbound_message(db,r,'111','Mándamelo en tres mensajes',external_id='isolated-failure')==''
        assert len(sent)==2

async def test_handoff_not_split(Session,monkeypatch):
    from app import service
    from app.agent import AgentResult
    sent=[]
    async def rates(*a):return None
    async def agent(*a):return AgentResult(reply='Primera\n\nSegunda\n\nTercera',action='handoff')
    async def send(phone,text):sent.append(text);return {'mock':True}
    monkeypatch.setattr(service,'refresh_rates',rates)
    monkeypatch.setattr(service,'run_agent',agent)
    monkeypatch.setattr(service,'send_whatsapp_message',send)
    async with Session() as db:
        r=Restaurant(name='Bizza',slug='bizza',pin='test');db.add(r);await db.commit()
        await service.handle_inbound_message(db,r,'111','Mándamelo en tres mensajes',external_id='isolated-handoff')
        assert sent==['Primera\n\nSegunda\n\nTercera']
