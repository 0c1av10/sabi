import asyncio,hashlib,hmac,json
from unittest.mock import AsyncMock
import pytest
from sqlalchemy import select,func
from app.inbound_receipts import claim_inbound
from app.models import InboundReceipt,Restaurant,MenuItem
from app import concierge
from app.config import settings

@pytest.mark.asyncio
async def test_concurrent_claims_one_winner(Session):
    async def claim():
        async with Session() as db:return await claim_inbound(db,'zernio','59900','same')
    assert sum(await asyncio.gather(claim(),claim(),claim()))==1

@pytest.mark.asyncio
async def test_cross_provider_platform_id_and_legitimate_repeats(Session):
    async with Session() as db:
        assert await claim_inbound(db,'meta','59900','wamid.one',platform_id='wamid.one')
        assert not await claim_inbound(db,'zernio','59900','different',platform_id='wamid.one')
        assert await claim_inbound(db,'zernio','59900','different2',platform_id='wamid.two')
        assert await claim_inbound(db,'zernio','59901','different',platform_id='wamid.one')
        assert not await claim_inbound(db,'zernio','59900',None)

@pytest.mark.asyncio
async def test_zernio_duplicate_greeting_one_reply(client,monkeypatch):
    from app.routers import webhook
    monkeypatch.setattr(settings,'zernio_webhook_secret','offline')
    sender=AsyncMock();monkeypatch.setattr(webhook,'send_whatsapp_message',sender)
    msg={'event':'message.received','message':{'id':'internal1','platformMessageId':'wamid.hello1','direction':'incoming','platform':'whatsapp','sender':{'phoneNumber':'59900000000'},'text':'Hola'}}
    async def post():
        raw=json.dumps(msg).encode();return await client.post('/webhook/zernio',content=raw,headers={'X-Zernio-Signature':hmac.new(b'offline',raw,hashlib.sha256).hexdigest()})
    assert (await post()).status_code==200
    assert (await post()).json()['status']=='duplicate_or_unidentified'
    assert sender.await_count==1
    msg['message']['id']='internal2';msg['message']['platformMessageId']='wamid.hello2'
    await post();assert sender.await_count==2 # same words, genuinely new message

@pytest.mark.asyncio
async def test_claim_survives_failed_processing_without_repeat(client,monkeypatch):
    from app.routers import webhook
    monkeypatch.setattr(settings,'zernio_webhook_secret','offline')
    route=AsyncMock(side_effect=RuntimeError('uncertain downstream'));monkeypatch.setattr(webhook,'_pilot_route',route)
    raw=json.dumps({'event':'message.received','message':{'id':'fail1','direction':'incoming','platform':'whatsapp','sender':{'phoneNumber':'59900000000'},'text':'Hola'}}).encode()
    headers={'X-Zernio-Signature':hmac.new(b'offline',raw,hashlib.sha256).hexdigest()}
    with pytest.raises(RuntimeError):await client.post('/webhook/zernio',content=raw,headers=headers)
    assert (await client.post('/webhook/zernio',content=raw,headers=headers)).status_code==200
    assert route.await_count==1

@pytest.mark.asyncio
async def test_cuisine_matches_menu_without_closed_catalog(Session):
    async with Session() as db:
        rows=[Restaurant(name=n,slug=s,pin='test') for n,s in [('NACIONAL Restaurante','nacional'),('Bizza','bizza'),('Oura','oura'),('Beijing Lechería','beijing-lecheria'),('La Esquina','la-esquina')]]
        db.add_all(rows);await db.flush()
        db.add(MenuItem(restaurant_id=rows[1].id,name='Margherita',category='Pizzas',price=12,available=True))
        db.add(MenuItem(restaurant_id=rows[0].id,name='Pollo asado',category='Criollo',price=10,available=True))
        db.add(MenuItem(restaurant_id=rows[4].id,name='Pastelito de Pizza',category='Pastelitos',price=2,available=True))
        await db.commit()
        text=await concierge.recommendations(db,pick=20)
        # La Esquina is a hidden demo business (docs/VISIBLE_RESTAURANTS.md): stored, not listed.
        assert all(n in text for n in ['NACIONAL','Bizza','Oura','Beijing']) and 'La Esquina' not in text
        text=await concierge.recommendations(db,body='Me interesa comida italiana')
        assert 'Bizza' in text and 'NACIONAL' not in text and 'La Esquina' not in text and 'pollo' not in text.lower()
        assert await db.scalar(select(func.count()).select_from(Restaurant))==5

@pytest.mark.asyncio
async def test_italian_no_verified_menu_no_random_substitute(Session):
    async with Session() as db:
        r=Restaurant(name='Pollo',slug='pollo',pin='test');db.add(r);await db.flush()
        db.add(MenuItem(restaurant_id=r.id,name='Pollo asado',category='Comida',price=10,available=True));await db.commit()
        text,_=await concierge.reply(db,'Me interesa comida italiana')
        assert 'No tengo un menú italiano verificado' in text and '•' not in text

@pytest.mark.asyncio
async def test_meta_duplicate_before_all_routes(client,monkeypatch):
    from app.routers import webhook
    send=AsyncMock();monkeypatch.setattr(webhook,'send_whatsapp_message',send)
    reaction=AsyncMock();monkeypatch.setattr(webhook,'_react',reaction)
    data={'entry':[{'changes':[{'value':{'messages':[{'id':'wamid.meta1','type':'text','from':'59900000000','text':{'body':'hola'}}]}}]}]}
    await client.post('/webhook/whatsapp',json=data);await client.post('/webhook/whatsapp',json=data)
    assert send.await_count==1 and reaction.await_count==1

@pytest.mark.asyncio
async def test_kapso_duplicate_before_routes(client,monkeypatch):
    from app.routers import webhook
    monkeypatch.setattr(settings,'kapso_webhook_secret','offline')
    send=AsyncMock();monkeypatch.setattr(webhook,'send_whatsapp_message',send)
    raw=json.dumps({'message':{'id':'kapso1','type':'text','from':'59900000000','text':{'body':'hola'}}}).encode()
    headers={'X-Webhook-Event':'whatsapp.message.received','X-Webhook-Signature':hmac.new(b'offline',raw,hashlib.sha256).hexdigest()}
    await client.post('/webhook/kapso',content=raw,headers=headers);await client.post('/webhook/kapso',content=raw,headers=headers)
    assert send.await_count==1
