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
