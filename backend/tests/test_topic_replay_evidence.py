"""Same real router sequence on baseline/candidate; model and outbound blocked."""
import json,os
from pathlib import Path
import pytest
from app.routers import webhook
from app import cinema_whatsapp as w
from app.config import settings
from app.models import Restaurant,utcnow
from app.event_models import EventSession

async def test_topic_replay(Session,monkeypatch):
    captured=[]
    async def send(*a,**kw):captured.append(a);return True
    async def no(*a,**kw):return False
    async def cinema(*a,**kw):return 'ROUTE_CINEMA_MODEL_BLOCKED'
    monkeypatch.setattr(webhook,'send_whatsapp_message',send)
    monkeypatch.setattr(webhook,'handle_cinema_whatsapp',cinema)
    monkeypatch.setattr(webhook.gym_whatsapp,'wants_gym',no)
    monkeypatch.setattr(settings,'cinema_mcp_enabled',True)
    turns=[]
    async with Session() as db:
        db.add(Restaurant(name='Bizza',slug='bizza',pin='test-only'))
        db.add(EventSession(id=w.session_id_for('111'),channel='cinema',updated_at=utcnow()))
        await db.commit()
        r,_,_=await webhook._resolve(db,'111','De bizza cuál es el horario')
        turns.append({'input':'De bizza cuál es el horario','route':'restaurant:'+r.name})
        for text in ['Sabes que es abruzzos','Es una pizzería famosa en lechería en la avenida principal','Búscala']:
            reply=await webhook._events_route(db,'111',text)
            turns.append({'input':text,'reply':reply})
    candidate=hasattr(webhook,'conversation_focus')
    assert all((t.get('reply')!='ROUTE_CINEMA_MODEL_BLOCKED')==candidate for t in turns[1:])
    out=os.environ.get('SABI_REPLAY_EVIDENCE')
    if out:Path(out).write_text(json.dumps({'candidate':candidate,'outbound':'fake transport only','model':'blocked before invocation','turns':turns},ensure_ascii=False,indent=2))
