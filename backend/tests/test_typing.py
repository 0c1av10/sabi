import httpx
import pytest
from app import whatsapp as w
from app.config import settings

@pytest.mark.parametrize('payload,expected',[({'success':True},True),({'success':False},False),({},False)])
async def test_typing_honors_success(monkeypatch,payload,expected):
    monkeypatch.setattr(settings,'whatsapp_mock_mode',False)
    monkeypatch.setattr(settings,'whatsapp_provider','zernio')
    monkeypatch.setattr(settings,'zernio_native_typing',True)
    w.zernio_conversations['123']='conversation'
    hits=[]
    def h(req):hits.append(req);return httpx.Response(200,json=payload)
    real=httpx.AsyncClient
    monkeypatch.setattr(w.httpx,'AsyncClient',lambda **k:real(transport=httpx.MockTransport(h)))
    assert await w.send_whatsapp_typing('123') is expected
    assert len(hits)==1 and hits[0].url.path.endswith('/conversation/typing')

async def test_typing_mock_no_http(monkeypatch):
    monkeypatch.setattr(settings,'whatsapp_mock_mode',True)
    assert await w.send_whatsapp_typing('123') is False

async def test_typing_failure_no_break(monkeypatch):
    monkeypatch.setattr(settings,'whatsapp_mock_mode',False)
    monkeypatch.setattr(settings,'whatsapp_provider','zernio')
    monkeypatch.setattr(settings,'zernio_native_typing',True)
    w.zernio_conversations['123']='conversation'
    def h(req):raise httpx.ConnectError('offline')
    real=httpx.AsyncClient
    monkeypatch.setattr(w.httpx,'AsyncClient',lambda **k:real(transport=httpx.MockTransport(h)))
    assert await w.send_whatsapp_typing('123') is False
