import pytest
from app import conversation_focus as f
from app import cinema_whatsapp as w
from app.place_directory import lookup

async def test_complete_sequence(Session,monkeypatch):
    from app.event_models import EventSession
    from app.models import utcnow,Restaurant
    from app.routers import webhook
    sends=[]
    async def blocked(*args,**kwargs):sends.append(args);return True
    monkeypatch.setattr(webhook,'send_whatsapp_message',blocked)
    async with Session() as db:
        db.add(EventSession(id=w.session_id_for('111'),channel='cinema',updated_at=utcnow()))
        db.add(Restaurant(name='Bizza',slug='bizza',pin='test-only',opening_hours=''))
        await db.commit()
        await f.set_focus(db,'111','cinema')
        # Actual trigger: named restaurant changes active focus while old cinema session survives.
        restaurant,_,reply=await webhook._resolve(db,'111','De bizza cuál es el horario')
        assert restaurant.name=='Bizza' and reply is None
        assert not await w.wants_cinema(db,'111','Sabes que es abruzzos')
        a=await webhook._events_route(db,'111','Sabes que es abruzzos')
        b=await webhook._events_route(db,'111','Es una pizzería famosa en lechería en la avenida principal')
        c=await webhook._events_route(db,'111','Búscala')
        assert 'ciudad' in a and 'Lechería' in b and "Abruzzo's" in c and 'KIA' in c
        assert 'threads.com' in c and 'no está conectada' not in c
        assert all('Supercines' not in x for x in [a,b,c])
        assert not await w.wants_cinema(db,'111','Búscala')
        assert await f.get(db,'222') is None
        assert await w.wants_cinema(db,'111','Quiero ir al cine')
        assert len(sends)==3

def test_stale_never_presented_as_current():
    from datetime import datetime,timezone
    assert 'necesita una consulta nueva' in lookup('abruzzos','Lechería',datetime(2026,11,19,tzinfo=timezone.utc))
    assert 'automática aún no está conectada' in lookup('otro','Lechería')
