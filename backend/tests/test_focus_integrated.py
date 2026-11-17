from datetime import timedelta
import asyncio
from app import conversation_focus as f
from app.models import utcnow

async def test_durable_expiry_isolation_and_forget(Session):
    now=utcnow()
    async with Session() as db:
        await f.save(db,'111',domain='shopping',entity='laptop Dell',platform='Yummy Marketplace',now=now)
    async with Session() as db:
        row=await f.get(db,'111',now=now+timedelta(minutes=29))
        assert row.entity=='laptop Dell' and row.platform=='Yummy Marketplace'
        assert await f.get(db,'222',now=now) is None
        assert await f.get(db,'111',now=now+timedelta(minutes=30)) is None
        await f.forget(db,'111')
        assert await f.get(db,'111',now=now) is None

async def test_old_write_cannot_overwrite_new_focus(Session):
    now=utcnow()
    async with Session() as db:
        await f.save(db,'111',domain='shopping',entity='laptop Dell',now=now)
    async with Session() as db:
        await f.save(db,'111',domain='cinema',entity='old',now=now-timedelta(seconds=1))
        assert (await f.get(db,'111',now=now)).domain=='shopping'

async def test_parallel_first_write_single_row(Session):
    async def put(entity):
        async with Session() as db:await f.save(db,'111',domain='place',entity=entity)
    await asyncio.gather(put('A'),put('B'))
    async with Session() as db:assert (await f.get(db,'111')).entity in ('A','B')

async def test_real_place_sequence_explicit_city_no_fake_search(Session):
    async with Session() as db:
        assert 'ciudad' in await f.place_reply(db,'111','Sabes que es abruzzos')
    async with Session() as db:
        b=await f.place_reply(db,'111','Es una pizzería famosa en Lechería en la avenida principal')
        assert 'Lechería' in b
        c=await f.place_reply(db,'111','Búscala')
        assert 'abruzzos' in c and 'Lechería' in c and 'aún no está conectada' in c
        assert (await f.get(db,'111')).city=='Lechería'
        assert await f.get(db,'222') is None

async def test_reset_forget_does_not_resurrect_stale_cinema(Session,monkeypatch):
    from app.routers import webhook
    from app.event_models import EventSession
    from app import memory,cinema_whatsapp as w
    from app.config import settings
    monkeypatch.setattr(settings,'cinema_mcp_enabled',True)
    async def send(*a):return True
    monkeypatch.setattr(webhook,'send_whatsapp_message',send)
    async with Session() as db:
        await memory.note(db,'111','Me llamo Ana')
        db.add(EventSession(id=w.session_id_for('111'),channel='cinema',updated_at=utcnow()))
        await db.commit()
        await f.save(db,'111',domain='shopping',entity='laptop Dell')
        await webhook._events_route(db,'111','Olvida el contexto')
        assert (await memory.get(db,'111')).name=='Ana'
        assert await f.get(db,'111') is None
        assert not await w.wants_cinema(db,'111','y mañana')
        await webhook._events_route(db,'111','Olvídame')
        assert await memory.get(db,'111') is None
        assert not await w.wants_cinema(db,'111','y mañana')

async def test_old_cinema_answer_not_sent_after_new_shopping(Session,monkeypatch):
    from app import cinema_whatsapp as w
    from app.config import settings
    monkeypatch.setattr(settings,'cinema_mcp_enabled',True)
    started=asyncio.Event();resume=asyncio.Event();sent=[]
    async def model(*a,**k):started.set();await resume.wait();return 'OLD_CINEMA_RESULT'
    async def send(*a):sent.append(a);return True
    monkeypatch.setattr(w,'run_cinema_agent',model)
    monkeypatch.setattr(w,'send_whatsapp_message',send)
    async def first():
        async with Session() as db:return await w.handle_cinema_whatsapp(db,'111','Quiero ir al cine')
    task=asyncio.create_task(first());await started.wait()
    async with Session() as db:await f.save(db,'111',domain='shopping',entity='Dell')
    resume.set();assert await task==''
    assert sent==[]
