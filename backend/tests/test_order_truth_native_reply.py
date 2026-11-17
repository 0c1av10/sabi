"""Offline coverage only. No live WhatsApp, payment or restaurant calls."""
import asyncio
from unittest.mock import AsyncMock

import httpx
import pytest
from sqlalchemy import select

from app import service, whatsapp
from app.agent import AgentResult
from app.config import settings
from app.models import MenuItem, Order, PaymentStatus, Restaurant


@pytest.mark.asyncio
@pytest.mark.parametrize('reference,expected', [('', PaymentStatus.pending), ('claim123', PaymentStatus.submitted)])
async def test_save_before_ack_method_not_payment(Session, monkeypatch, reference, expected):
    async with Session() as db:
        r = Restaurant(name='Fixture Only', slug='fixture-only', owner_phone='', pin='unused')
        db.add(r)
        await db.flush()
        db.add(MenuItem(restaurant_id=r.id, name='Fixture Pizza', price=12, category='Pizza'))
        await db.commit()
        draft = {'items': [{'name': 'Fixture Pizza', 'quantity': 1}], 'order_type': 'retiro',
                 'payment_method': 'pago_movil', 'payment_reference': reference}
        monkeypatch.setattr(service, 'refresh_rates', AsyncMock())
        monkeypatch.setattr(service, 'run_agent', AsyncMock(return_value=AgentResult(
            reply='WRONG UNSAFE PROMISE', action='submit_order', order=draft, state={})))
        sent = []
        async def send(phone, text):
            async with Session() as independent:
                saved = (await independent.execute(select(Order))).scalar_one()
                assert saved.payment_status == expected
            sent.append(text)
            return {'mock': True}
        monkeypatch.setattr(service, 'send_whatsapp_message', send)
        reply = await service.handle_inbound_message(db, r, '000-test', 'Pago móvil')
        assert len(sent) == 1 and reply == sent[0]
        assert 'Registré tu solicitud #' in reply
        assert 'Aún no tengo confirmación' in reply
        assert 'no pagues basándote' in reply
        assert 'WRONG' not in reply and 'enseguida' not in reply


@pytest.mark.asyncio
async def test_failed_save_never_acknowledges_registration(Session, monkeypatch):
    async with Session() as db:
        r = Restaurant(name='Fixture', slug='fixture', pin='unused')
        db.add(r)
        await db.commit()
        monkeypatch.setattr(service, 'refresh_rates', AsyncMock())
        monkeypatch.setattr(service, 'run_agent', AsyncMock(return_value=AgentResult(
            reply='unsafe', action='submit_order', order={'anything': 1})))
        monkeypatch.setattr(service, 'create_pending_order', AsyncMock(side_effect=RuntimeError('offline failure')))
        send = AsyncMock()
        monkeypatch.setattr(service, 'send_whatsapp_message', send)
        with pytest.raises(RuntimeError):
            await service.handle_inbound_message(db, r, '000-test', 'Pago móvil')
        send.assert_not_awaited()


@pytest.mark.asyncio
async def test_reaction_zernio_correct_target_no_retry(monkeypatch):
    monkeypatch.setattr(settings, 'whatsapp_provider', 'zernio')
    monkeypatch.setattr(settings, 'whatsapp_mock_mode', False)
    monkeypatch.setattr(settings, 'zernio_native_reactions', True)
    monkeypatch.setitem(whatsapp.zernio_conversations, '000', 'test-conv')
    post = AsyncMock(return_value={'success': True})
    monkeypatch.setattr(whatsapp, '_post', post)
    await whatsapp.send_whatsapp_reaction('000', 'wamid.test/target', '👍')
    args = post.await_args.args
    assert args[1].endswith('/test-conv/messages/wamid.test%2Ftarget/reactions')
    assert args[2]['emoji'] == '👍'
    assert post.await_count == 1
    monkeypatch.setattr(settings, 'zernio_native_reactions', False)
    assert await whatsapp.send_whatsapp_reaction('000', 'wamid.test', '👍') == {'skipped': 'feature_disabled'}
    assert post.await_count == 1


@pytest.mark.asyncio
async def test_quote_platform_id_and_never_cross_recipient(monkeypatch):
    monkeypatch.setattr(settings, 'whatsapp_quote_replies', True)
    monkeypatch.setitem(whatsapp.zernio_conversations, '000', 'conv0')
    monkeypatch.setitem(whatsapp.zernio_conversations, '111', 'conv1')
    post = AsyncMock(return_value={'success': True})
    monkeypatch.setattr(whatsapp, '_post', post)
    async with httpx.AsyncClient() as client:
        with whatsapp.incoming_reply_context('000', 'wamid.original'):
            await whatsapp._send_zernio(client, '000', 'Reply')
            assert post.await_args.args[2]['replyTo'] == 'wamid.original'
            await whatsapp._send_zernio(client, '111', 'Owner notification')
            assert 'replyTo' not in post.await_args.args[2]
        assert whatsapp._quote_target('000') == ''
        with whatsapp.incoming_reply_context('000', 'zernio-internal-id'):
            await whatsapp._send_zernio(client, '000', 'Reply')
            assert 'replyTo' not in post.await_args.args[2]


@pytest.mark.asyncio
async def test_context_isolation_and_cleanup(monkeypatch):
    monkeypatch.setattr(settings, 'whatsapp_quote_replies', True)
    async def one(phone):
        with whatsapp.incoming_reply_context(phone, 'wamid.' + phone):
            await asyncio.sleep(0)
            assert whatsapp._quote_target(phone) == 'wamid.' + phone
            assert whatsapp._quote_target('999') == ''
        assert whatsapp._quote_target(phone) == ''
    await asyncio.gather(one('000'), one('111'))


def test_plain_text_keeps_prices_accents_newlines():
    assert whatsapp.plain_message('¡Hola! 👋\n1 x Pizza 🍕 $12,50 · Bs 10.000,00\nGracias 🙌🏽') == (
        '¡Hola!\n1 x Pizza $12,50 · Bs 10.000,00\nGracias')
    assert whatsapp.plain_message('Familia 👨‍👩‍👧‍👦 🇻🇪 1️⃣ café') == 'Familia café'

@pytest.mark.asyncio
async def test_redelivery_reacts_once_and_quotes_the_platform_id(client, monkeypatch):
    import hashlib
    import hmac
    import json
    from app.routers import webhook
    monkeypatch.setattr(settings, 'zernio_webhook_secret', 'offline')
    monkeypatch.setattr(settings, 'zernio_native_reactions', True)
    monkeypatch.setattr(settings, 'whatsapp_quote_replies', True)
    react = AsyncMock()
    monkeypatch.setattr(webhook, 'send_whatsapp_reaction', react)
    contexts = []
    async def send(phone, body):
        contexts.append(whatsapp._quote_target(phone))
    monkeypatch.setattr(webhook, 'send_whatsapp_message', send)
    data = {'event': 'message.received', 'message': {'id': 'internal-fixture',
            'conversationId': 'conv-fixture', 'platformMessageId': 'wamid.fixture',
            'direction': 'incoming', 'platform': 'whatsapp',
            'sender': {'phoneNumber': '000000'}, 'text': 'Hola'}}
    raw = json.dumps(data).encode()
    headers = {'X-Zernio-Signature': hmac.new(b'offline', raw, hashlib.sha256).hexdigest()}
    assert (await client.post('/webhook/zernio', content=raw, headers=headers)).status_code == 200
    assert (await client.post('/webhook/zernio', content=raw, headers=headers)).json()['status'] == 'duplicate_or_unidentified'
    assert react.await_count == 1
    assert react.await_args.args[1] == 'wamid.fixture'
    assert contexts == ['wamid.fixture']
    assert whatsapp._quote_target('000000') == ''


@pytest.mark.asyncio
async def test_plain_message_applied_at_actual_send_boundary(monkeypatch):
    monkeypatch.setattr(settings, 'whatsapp_mock_mode', True)
    monkeypatch.setattr(settings, 'whatsapp_plain_text', True)
    whatsapp.sent_log.clear()
    await whatsapp.send_whatsapp_message('000', 'Hola 👋\nPizza 🍕 $12,00')
    assert whatsapp.sent_log[-1]['body'] == 'Hola\nPizza $12,00'
