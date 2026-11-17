"""Contract tests only; no live Zernio requests, credentials or chargeable calls."""
import httpx
import pytest
from app import whatsapp as wa
from app.config import settings

PHONE = '584240000000'

@pytest.fixture
def configured(monkeypatch):
    monkeypatch.setattr(settings, 'whatsapp_provider', 'zernio')
    monkeypatch.setattr(settings, 'whatsapp_mock_mode', False)
    monkeypatch.setattr(settings, 'whatsapp_presence_enabled', True)
    monkeypatch.setattr(settings, 'whatsapp_presence_allowed_phones', PHONE)
    monkeypatch.setattr(settings, 'zernio_api_key', 'contract-test-only')
    monkeypatch.setattr(settings, 'zernio_account_id', 'account-test')
    monkeypatch.setitem(wa.zernio_conversations, PHONE, 'conv-test')

@pytest.fixture
def requests_spy(monkeypatch):
    calls=[]
    def handler(req):
        calls.append(req)
        return httpx.Response(200, json={'success': True})
    original=httpx.AsyncClient
    monkeypatch.setattr(wa.httpx, 'AsyncClient', lambda **kw: original(transport=httpx.MockTransport(handler), **kw))
    return calls

@pytest.mark.asyncio
async def test_disabled_has_no_http(configured, requests_spy, monkeypatch):
    monkeypatch.setattr(settings,'whatsapp_presence_enabled',False)
    assert 'skipped' in await wa.send_whatsapp_typing(PHONE)
    assert 'skipped' in await wa.send_whatsapp_reaction(PHONE,'message','👍')
    assert requests_spy == []

@pytest.mark.asyncio
async def test_unknown_phone_or_conversation_never_looked_up(configured, requests_spy, monkeypatch):
    assert 'skipped' in await wa.send_whatsapp_typing('584249999999')
    monkeypatch.delitem(wa.zernio_conversations, PHONE)
    assert 'skipped' in await wa.send_whatsapp_typing(PHONE)
    assert requests_spy == []

@pytest.mark.asyncio
async def test_typing_and_reaction_contract(configured,requests_spy):
    assert await wa.send_whatsapp_typing(PHONE)=={'accepted':True,'visible_verified':False}
    assert (await wa.send_whatsapp_reaction(PHONE,'message/test','👍'))['accepted']
    assert requests_spy[0].url.path.endswith('/conv-test/typing')
    assert '/messages/message%2Ftest/reactions' in str(requests_spy[1].url)
    import json
    assert json.loads(requests_spy[1].content)=={'accountId':'account-test','emoji':'👍'}

@pytest.mark.asyncio
async def test_mock_blocks_network(configured, requests_spy,monkeypatch):
    monkeypatch.setattr(settings,'whatsapp_mock_mode',True)
    assert (await wa.send_whatsapp_typing(PHONE))['mock']
    assert (await wa.send_whatsapp_reaction(PHONE,'message','👍'))['mock']
    assert requests_spy==[]

@pytest.mark.asyncio
async def test_200_false_not_success(configured,monkeypatch):
    original=httpx.AsyncClient
    monkeypatch.setattr(wa.httpx,'AsyncClient',lambda **kw: original(transport=httpx.MockTransport(lambda req:httpx.Response(200,json={'success':False})),**kw))
    assert not (await wa.send_whatsapp_typing(PHONE))['accepted']

@pytest.mark.asyncio
async def test_errors_never_retry(configured,monkeypatch):
    calls=[]
    original=httpx.AsyncClient
    def handler(req):
        calls.append(req)
        raise httpx.ReadTimeout('timeout')
    monkeypatch.setattr(wa.httpx,'AsyncClient',lambda **kw:original(transport=httpx.MockTransport(handler),**kw))
    assert (await wa.send_whatsapp_typing(PHONE))['error']=='presence_outcome_unknown'
    assert len(calls)==1

@pytest.mark.asyncio
async def test_signed_webhook_presence_routes_locally(client,configured,monkeypatch):
    import hashlib,hmac,json
    from app.routers import webhook
    calls=[]
    async def typing(phone):calls.append(('typing',phone));return {'mock':True}
    async def reaction(phone,mid,emoji):calls.append(('reaction',mid,emoji));return {'mock':True}
    async def routed(*a,**kw):return True
    monkeypatch.setattr(settings,'zernio_webhook_secret','test-webhook-only')
    monkeypatch.setattr(webhook,'send_whatsapp_typing',typing)
    monkeypatch.setattr(webhook,'send_whatsapp_reaction',reaction)
    monkeypatch.setattr(webhook,'_pilot_route',routed)
    body={'event':'message.received','message':{'direction':'incoming','platform':'whatsapp','sender':{'phoneNumber':PHONE},'conversationId':'conv-test','id':'incoming-test','text':'gracias'}}
    raw=json.dumps(body).encode()
    signature=hmac.new(b'test-webhook-only',raw,hashlib.sha256).hexdigest()
    bad=await client.post('/webhook/zernio',content=raw,headers={'X-Zernio-Signature':'wrong'})
    assert bad.status_code==401 and calls==[]
    good=await client.post('/webhook/zernio',content=raw,headers={'X-Zernio-Signature':signature})
    assert good.status_code==200
    assert calls==[('typing',PHONE),('reaction','incoming-test','🙏')]
