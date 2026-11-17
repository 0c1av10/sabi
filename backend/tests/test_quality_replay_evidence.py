import os,json
from pathlib import Path
from app.routers import webhook
from app import memory,concierge,cinema_whatsapp as w
from app.models import Restaurant,utcnow
from app.event_models import EventSession
from app.config import settings

async def test_quality_replay(Session,monkeypatch):
    async def no(*a,**k):return False
    async def cinema(*a,**k):return 'CINEMA_ROUTE_MODEL_BLOCKED'
    sent=[]
    async def send(phone,text):sent.append(text);return True
    monkeypatch.setattr(settings,'cinema_mcp_enabled',True)
    monkeypatch.setattr(webhook,'handle_cinema_whatsapp',cinema)
    monkeypatch.setattr(webhook.gym_whatsapp,'wants_gym',no)
    monkeypatch.setattr(webhook,'wants_events',no)
    monkeypatch.setattr(webhook,'send_whatsapp_message',send)
    evidence=[]
    async with Session() as db:
        db.add(Restaurant(name='Criollo fixture',slug='criollo',pin='test-only',tagline='Pollo y cocina criolla'))
        db.add(EventSession(id=w.session_id_for('111'),channel='cinema',updated_at=utcnow()))
        await db.commit()
        await memory.note(db,'111','Me llamo Ana')
        await memory.note(db,'111','Dime entonces del cine Regina de puerto la cruz')
        evidence.append({'name_after_command':(await memory.get(db,'111')).name})
        for body in ['Hola','Sabi','Me interesa algo de comida china','Hola busca en marketplace','Cuánto sale una laptop Dell','Yummy marketplace']:
            reply=await webhook._events_route(db,'111',body)
            if reply is None:
                rest,_,reply=await webhook._resolve(db,'111',body)
                if rest:reply='RESTAURANT_ROUTE_MODEL_BLOCKED'
            evidence.append({'input':body,'reply':reply})
        assert await memory.get(db,'222') is None
    candidate=hasattr(concierge,'cuisine_request')
    assert evidence[0]['name_after_command']==('Ana' if candidate else 'Entonces')
    if candidate:assert all('CINEMA_ROUTE' not in (row.get('reply') or '') for row in evidence)
    out=os.environ.get('SABI_QUALITY_EVIDENCE')
    if out:Path(out).write_text(json.dumps({'candidate':candidate,'model':'blocked','outbound':'recording fake','observed':evidence},ensure_ascii=False,indent=2))
