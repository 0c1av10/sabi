from unittest.mock import AsyncMock
import pytest
from app import public_web_jobs as jobs
from app.config import settings
from app.models import PublicWebJob
from sqlalchemy import select

@pytest.fixture
def enabled(monkeypatch):
    monkeypatch.setattr(settings,'public_web_pilot_enabled',True)
    monkeypatch.setattr(settings,'public_web_allowed_phones','59900000000')
    monkeypatch.setattr(settings,'public_web_worker_token','offline-test-worker')
    monkeypatch.setattr(settings,'public_web_delivery_enabled',False)

@pytest.mark.asyncio
async def test_queue_claim_capture_no_send(Session,enabled,monkeypatch):
    send=AsyncMock();monkeypatch.setattr(jobs,'send_whatsapp_image',send)
    async with Session() as db:
        assert await jobs.enqueue(db,'59900000000','hola','hello') is None
        assert await jobs.enqueue(db,'59911111111','/web yummy audifonos','bad') is None
        reply=await jobs.enqueue(db,'59900000000','busca audifonos en yummy marketplace','msg-1')
        assert 'No' not in reply and 'Solo lectura' in reply
        duplicate=await jobs.enqueue(db,'59900000000','/web yummy audifonos','msg-1')
        assert 'duplico' in duplicate
        job=await jobs.claim(db);assert set(job)=={'id','site','query','claim'}
        assert await jobs.claim(db) is None
        result=await jobs.complete(db,job['id'],job['claim'],b'\xff\xd8\xffoffline-test')
        assert result=={'status':'captured_nosend','sent':False}
        send.assert_not_called()
        with pytest.raises(ValueError):await jobs.complete(db,job['id'],job['claim'],b'\xff\xd8\xffoffline-test')

@pytest.mark.asyncio
async def test_claim_auth_expiry_and_private_api(client,enabled):
    assert (await client.post('/api/pilot/public-web/claim')).status_code==401
    r=await client.post('/api/pilot/public-web/claim',headers={'Authorization':'Bearer offline-test-worker'})
    assert r.json()=={'job':None}
    assert (await client.get('/api/pilot/public-web/jobs/1/capture')).status_code==405

@pytest.mark.asyncio
async def test_disabled_is_noop(Session,monkeypatch):
    monkeypatch.setattr(settings,'public_web_pilot_enabled',False)
    async with Session() as db:
        assert await jobs.enqueue(db,'59900000000','/web yummy audifonos','off') is None
        assert (await db.execute(select(PublicWebJob))).first() is None

@pytest.mark.asyncio
async def test_wrong_claim_and_oversize_rejected(Session,enabled):
    async with Session() as db:
        await jobs.enqueue(db,'59900000000','/web mitickera natalia','msg-2');job=await jobs.claim(db)
        with pytest.raises(ValueError):await jobs.complete(db,job['id'],'wrong',b'\xff\xd8\xfftest')
        with pytest.raises(ValueError):await jobs.complete(db,job['id'],job['claim'],b'\xff\xd8\xff'+b'x'*1_000_000)

@pytest.mark.parametrize('body',['hola','pide taxi yummy','compra audifonos en yummy','busca https://evil.test en yummy','busca +584241234567 en yummy'])
def test_command_is_bounded(body):assert jobs.parse_command(body) is None

@pytest.mark.asyncio
async def test_signed_webhook_additive_queue_no_provider_send(client,Session,enabled,monkeypatch):
    import hashlib,hmac,json
    from app.routers import webhook
    monkeypatch.setattr(settings,'zernio_webhook_secret','offline-webhook-key')
    monkeypatch.setattr(settings,'whatsapp_presence_enabled',False)
    send=AsyncMock();monkeypatch.setattr(webhook,'send_whatsapp_message',send)
    payload={'event':'message.received','message':{'id':'offline-inbound-1','direction':'incoming','platform':'whatsapp','sender':{'phoneNumber':'59900000000'},'text':'/web yummy audifonos'}}
    raw=json.dumps(payload).encode();sig=hmac.new(b'offline-webhook-key',raw,hashlib.sha256).hexdigest()
    response=await client.post('/webhook/zernio',content=raw,headers={'X-Zernio-Signature':sig})
    assert response.status_code==200
    async with Session() as db:
        row=await db.scalar(select(PublicWebJob));assert row.query=='audifonos' and row.status=='pending'
    send.assert_not_called()
