import json,os
from pathlib import Path
from app import conversation_focus as focus,cinema_whatsapp
from app.auth import named_business_query
from app.routers import webhook

async def test_persisted_invalid_focus_does_not_survive_read(Session):
    async with Session() as db:
        await focus.save(db,'111',domain='place',entity='Mándamelo',city='tres mensajes')
        assert await focus.get(db,'111') is None
        await focus.save(db,'222',domain='place',entity='Mensajes',city='Valencia')
        assert (await focus.get(db,'222')).entity=='Mensajes'
        assert named_business_query('De los cines') is None

async def test_exact_capture_sequence_changes_domain_without_live_model(Session,monkeypatch):
    sent=[];queries=[]
    async def send(phone,text):sent.append(text);return {'mock':True}
    async def run(body,history=None):
        queries.append(body)
        return 'No tengo una cartelera confirmada para mostrarte en Puerto La Cruz.'
    monkeypatch.setattr(webhook,'send_whatsapp_message',send)
    monkeypatch.setattr(cinema_whatsapp,'send_whatsapp_message',send)
    monkeypatch.setattr(cinema_whatsapp,'run_cinema_agent',run)
    monkeypatch.setattr(cinema_whatsapp.settings,'cinema_mcp_enabled',True)
    async with Session() as db:
        await focus.save(db,'111',domain='place',entity='Mándamelo',city='tres mensajes')
        evidence=[]
        for body in ['Que hay para ver en plc','Puerto la cruz','De los cines']:
            reply=await webhook._events_route(db,'111',body)
            assert 'Puerto La Cruz' in reply and 'Mándamelo' not in reply
            evidence.append({'input':body,'reply':reply})
        assert len(queries)==2 and all('Ciudad explícita para esta consulta: Puerto La Cruz.' in q for q in queries)
        assert (await focus.get(db,'111')).city=='Puerto La Cruz'
        if os.environ.get('SABI_CITY_EVIDENCE'):Path(os.environ['SABI_CITY_EVIDENCE']).write_text(json.dumps(evidence,ensure_ascii=False,indent=2))

async def test_real_place_can_switch_to_explicit_cinema(Session,monkeypatch):
    called=[]
    async def wants(*args):return True
    async def handle(db,phone,body,*args):called.append(body);return 'cine simulado'
    monkeypatch.setattr(webhook,'wants_cinema',wants)
    monkeypatch.setattr(webhook,'handle_cinema_whatsapp',handle)
    async with Session() as db:
        await focus.save(db,'111',domain='place',entity='Acme',city='Valencia')
        assert await webhook._events_route(db,'111','De los cines')=='cine simulado'
        assert called==['De los cines']
        assert (await focus.get(db,'111')).domain=='cinema'

async def test_asked_city_plc_embedded_greeting_and_complaint(Session,monkeypatch):
    queries=[];sent=[]
    async def send(phone,text):sent.append(text);return {'mock':True}
    async def run(body,history=None):
        queries.append(body)
        if len(queries)==1:return '¿En qué ciudad te gustaría ver la cartelera?'
        return 'No tengo una cartelera confirmada para mostrarte en Puerto La Cruz.'
    monkeypatch.setattr(webhook,'send_whatsapp_message',send)
    monkeypatch.setattr(cinema_whatsapp,'send_whatsapp_message',send)
    monkeypatch.setattr(cinema_whatsapp,'run_cinema_agent',run)
    monkeypatch.setattr(cinema_whatsapp.settings,'cinema_mcp_enabled',True)
    async with Session() as db:
        evidence=[]
        for body in ['quiero ver la cartelera de cine','plc','alo, puerto la cruz','que paso no entiendes?']:
            reply=await webhook._events_route(db,'111',body)
            assert reply and 'Hola de nuevo' not in reply
            evidence.append({'input':body,'reply':reply})
        assert (await focus.get(db,'111')).city=='Puerto La Cruz'
        assert len(queries)==3 and all('Ciudad explícita para esta consulta: Puerto La Cruz.' in q for q in queries[1:])
        if os.environ.get('SABI_CITY_EVIDENCE'):Path(os.environ['SABI_CITY_EVIDENCE']).with_name('sabi-city-answer-evidence.json').write_text(json.dumps(evidence,ensure_ascii=False,indent=2))

async def test_plc_without_cinema_context_is_not_assumed(Session,monkeypatch):
    async with Session() as db:
        assert await webhook._events_route(db,'111','plc') is None
        assert await focus.get(db,'111') is None
