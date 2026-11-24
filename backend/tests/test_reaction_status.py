import pytest,httpx
from app.reactions import reaction_for
from app import whatsapp as w

@pytest.mark.parametrize('body',['Quiero ir al cine','Cartelera en PLC','Qué películas hay?','Hola, quiero cine'])
def test_cinema_ticket_precedes_food_or_greeting(body):assert reaction_for(body)=='🎟️'

@pytest.mark.parametrize('body,emoji',[('gracias por la cartelera','🙏'),('problema con las entradas de cine','😔'),('quiero pizza','🍽️'),('estoy pensando',None)])
def test_priorities_and_no_fake_processing(body,emoji):assert reaction_for(body)==emoji


async def test_removal_mock_has_exact_message(monkeypatch):
    monkeypatch.setattr(w.settings,'whatsapp_mock_mode',True)
    before=len(w.sent_log)
    assert (await w.remove_whatsapp_reaction('111','wamid.test'))['mock']
    assert w.sent_log[before:]==[{'to':'111','reaction_removed':True,'message_id':'wamid.test'}]

async def test_zernio_removal_contract_without_live_send(monkeypatch):
    monkeypatch.setattr(w.settings,'whatsapp_mock_mode',False)
    monkeypatch.setattr(w.settings,'whatsapp_provider','zernio')
    monkeypatch.setattr(w.settings,'zernio_native_reactions',True)
    monkeypatch.setattr(w.settings,'zernio_account_id','test-account')
    monkeypatch.setitem(w.zernio_conversations,'111','test-conversation')
    seen=[]
    def handler(request):
        seen.append(request)
        return httpx.Response(200,json={'success':True})
    real_client=httpx.AsyncClient
    monkeypatch.setattr(w.httpx,'AsyncClient',lambda **kw:real_client(transport=httpx.MockTransport(handler),**kw))
    assert await w.remove_whatsapp_reaction('111','wamid.exact=')=={'success':True}
    assert len(seen)==1 and seen[0].method=='DELETE'
    assert '/test-conversation/messages/wamid.exact%3D/reactions' in str(seen[0].url)
    assert seen[0].url.params['accountId']=='test-account'

async def test_no_unsupported_provider_or_missing_destination(monkeypatch):
    monkeypatch.setattr(w.settings,'whatsapp_mock_mode',False)
    monkeypatch.setattr(w.settings,'whatsapp_provider','zernio')
    assert (await w.remove_whatsapp_reaction('222','wamid.test'))['skipped']=='no_inbound_conversation'
    monkeypatch.setattr(w.settings,'whatsapp_provider','meta')
    assert (await w.remove_whatsapp_reaction('111','wamid.test'))['skipped']=='removal_not_verified_for_provider'


import hashlib, hmac, json
from unittest.mock import AsyncMock

@pytest.mark.asyncio
@pytest.mark.parametrize('text,removed', [('¿Qué tienen en el menú?', True), ('Hola', False)])
async def test_looking_reaction_is_cleared_after_the_reply(client, monkeypatch, text, removed):
    from app.routers import webhook
    monkeypatch.setattr(w.settings, 'zernio_webhook_secret', 'offline')
    monkeypatch.setattr(w.settings, 'zernio_native_reactions', True)
    events = []
    async def react(phone, mid, emoji): events.append(('react', mid, emoji))
    async def remove(phone, mid): events.append(('remove', mid))
    async def send(phone, body): events.append(('reply',))
    monkeypatch.setattr(webhook, 'send_whatsapp_reaction', react)
    monkeypatch.setattr(webhook, 'remove_whatsapp_reaction', remove)
    monkeypatch.setattr(webhook, 'send_whatsapp_message', send)
    data = {'event': 'message.received', 'message': {'id': 'internal-' + text, 'conversationId': 'conv-x',
            'platformMessageId': 'wamid.x', 'direction': 'incoming', 'platform': 'whatsapp',
            'sender': {'phoneNumber': '000111'}, 'text': text}}
    raw = json.dumps(data).encode()
    headers = {'X-Zernio-Signature': hmac.new(b'offline', raw, hashlib.sha256).hexdigest()}
    assert (await client.post('/webhook/zernio', content=raw, headers=headers)).status_code == 200
    assert events[0][0] == 'react' and ('reply',) in events
    if removed:
        assert events[0][2] == '👀' and events[-1] == ('remove', 'wamid.x')
    else:
        assert all(e[0] != 'remove' for e in events)
