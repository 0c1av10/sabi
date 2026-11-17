import pytest
from app import memory,concierge,cinema_whatsapp as w
from app.models import Restaurant

def test_real_name_contamination_no_model():
    assert memory.extract_name('Dime entonces del cine Regina de puerto la cruz')==''
    assert memory.extract_name('Me llamo Ana')=='Ana'
    assert memory.first_name('Entonces')=='Entonces'  # Never hide a stored name without provenance.

async def test_vocative_no_cinema_no_model(monkeypatch):
    async def no(*a,**k):raise AssertionError('must not query a cinema or merchant')
    monkeypatch.setattr(w,'restaurant_by_mention',no)
    assert not await w.wants_cinema(None,'111','Sabi')
    assert (await concierge.reply(None,'Sabi'))[0]=='Aquí estoy. ¿En qué te ayudo?'

async def test_chinese_constraint_with_unrelated_catalog(Session):
    async with Session() as db:
        db.add_all([Restaurant(name='Criollo de prueba',slug='fixture-criollo',pin='test-only',tagline='Pollo a la brasa y cocina criolla'),Restaurant(name='Arepas de prueba',slug='fixture-arepas',pin='test-only',tagline='Arepas y pastelitos')])
        await db.commit()
        r=await concierge.recommendations(db,body='Me interesa algo de comida china')
        assert 'No tengo un local de comida china verificado' in r
        assert 'Te sugiero' not in r and 'armo el pedido' not in r

@pytest.mark.parametrize('body',['comida rica','comida sabrosa','comida saludable'])
def test_descriptive_adjectives_not_cuisines(body):
    assert concierge.cuisine_request(body)==('',False)

@pytest.mark.parametrize('body',['cocina marciana','comida de zyxw'])
def test_unknown_cuisine_requires_clarification(body):
    assert concierge.cuisine_request(body)==('',True)

async def test_name_isolation_and_persistence(Session):
    async with Session() as db:
        await memory.note(db,'111','Me llamo Ana')
        await memory.note(db,'222','Me llamo Luis')
        await memory.note(db,'111','Dime entonces del cine Regina de puerto la cruz')
    async with Session() as db:
        assert (await memory.get(db,'111')).name=='Ana'
        assert (await memory.get(db,'222')).name=='Luis'

async def test_no_catalog_no_fabricated_cuisine(Session):
    async with Session() as db:
        r=await concierge.recommendations(db,body='comida china')
        assert 'Te sugiero' not in r and 'armo el pedido' not in r

async def test_constraint_not_bypassed_by_multiple_product_matches(Session,monkeypatch):
    async def forbidden(*a):raise AssertionError('product matching must not bypass cuisine constraint')
    monkeypatch.setattr(concierge,'restaurants_by_product',forbidden)
    async with Session() as db:
        db.add(Restaurant(name='Local fixture',slug='fixture',pin='test-only',tagline='Cocina criolla'))
        await db.commit()
        reply,_=await concierge.reply(db,'Me interesa algo de comida china')
        assert 'No tengo un local de comida china verificado' in reply

def test_normal_menu_transfer_is_not_handoff():
    from app.agent import guard_representation,AgentResult
    result=guard_representation(AgentResult(reply='Te paso el menú para que elijas'),Restaurant(name='Bizza'))
    assert result.reply=='Te paso el menú para que elijas' and result.action=='continue'

@pytest.mark.parametrize('text,cuisine',[
    ('Me provoca sushi','japonesa'),('Quiero algo mexicano','mexicana'),
    ('¿Restaurantes chinos por aquí?','china'),('Quiero probar cocina árabe','arabe'),
    ('¿Tienes comida venezolana?','venezolana'),('Me provoca italiana','italiana'),
    ('Busco restaurante japonés','japonesa'),('Algo peruano','peruana')])
def test_natural_cuisine_variety(text,cuisine):
    assert concierge.cuisine_request(text)==(cuisine,False)

@pytest.mark.parametrize('text',['No quiero comida china','China o japonesa','Cocina marciana'])
def test_unclear_or_multiple_preferences_ask_not_random(text):
    assert concierge.cuisine_request(text)==('',True)

async def test_consolidated_screenshot_routing(Session,monkeypatch):
    from app.routers import webhook
    from app.event_models import EventSession
    from app.models import utcnow
    async def no(*a,**k):return False
    async def forbidden(*a,**k):raise AssertionError('no cinema model or outbound allowed')
    monkeypatch.setattr(webhook.gym_whatsapp,'wants_gym',no)
    monkeypatch.setattr(webhook,'handle_cinema_whatsapp',forbidden)
    monkeypatch.setattr(webhook,'send_whatsapp_message',forbidden)
    from app.config import settings
    monkeypatch.setattr(settings,'cinema_mcp_enabled',True)
    async with Session() as db:
        db.add(EventSession(id=w.session_id_for('111'),channel='cinema',updated_at=utcnow()))
        db.add(Restaurant(name='Local Criollo',slug='criollo',pin='test-only',tagline='Cocina criolla'))
        await db.commit()
        await memory.note(db,'111','Me llamo Ana')
        await memory.set_topic(db,'111','cine')
        await memory.note(db,'111','Dime entonces del cine Regina de puerto la cruz')
        assert await webhook._events_route(db,'111','Sabi') is None
        assert (await concierge.reply(db,'Sabi','111'))[0]=='Aquí estoy. ¿En qué te ayudo?'
        assert await webhook._events_route(db,'111','Me interesa algo de comida china') is None
        rest,_,reply=await webhook._resolve(db,'111','Me interesa algo de comida china')
        assert rest is None and 'No tengo un local de comida china verificado' in reply
        assert (await memory.get(db,'111')).name=='Ana'
        # Restaurant topic supersedes the stale cinema session, without deleting old facts.
        assert not await w.wants_cinema(db,'111','Búscala')
        assert await w.wants_cinema(db,'111','Quiero volver al cine')
        assert await memory.get(db,'222') is None

@pytest.mark.parametrize('text',['Hola busca en marketplace','Cuánto sale una laptop Dell','Sabes que es abruzzos','Es una pizzería famosa en lechería en la avenida principal','Búscala','Ayúdame con un trabajo'])
async def test_active_cinema_is_not_a_catch_all(Session,monkeypatch,text):
    from app.config import settings
    from app.event_models import EventSession
    from app.models import utcnow
    monkeypatch.setattr(settings,'cinema_mcp_enabled',True)
    async with Session() as db:
        db.add(EventSession(id=w.session_id_for('111'),channel='cinema',updated_at=utcnow()))
        await db.commit()
        assert not await w.wants_cinema(db,'111',text)

async def test_new_task_keeps_actual_name_and_does_not_search_vocative(Session,monkeypatch):
    from app.routers import webhook
    from app.event_models import EventSession
    from app.models import utcnow
    from app.config import settings
    monkeypatch.setattr(settings,'cinema_mcp_enabled',True)
    async def no(*a,**k):return False
    async def forbidden(*a,**k):raise AssertionError('must not invoke cinema model or live send')
    monkeypatch.setattr(webhook.gym_whatsapp,'wants_gym',no)
    monkeypatch.setattr(webhook,'handle_cinema_whatsapp',forbidden)
    monkeypatch.setattr(webhook,'send_whatsapp_message',forbidden)
    async with Session() as db:
        db.add(EventSession(id=w.session_id_for('111'),channel='cinema',updated_at=utcnow()))
        await db.commit()
        await memory.note(db,'111','Me llamo Ana')
        for body in ['Dime entonces del cine Regina de puerto la cruz']:
            # Name state update independent of paid domain execution.
            await memory.note(db,'111',body)
        for body in ['Sabi']:
            assert await webhook._events_route(db,'111',body) is None
        assert (await memory.get(db,'111')).name=='Ana'

async def test_marketplace_product_sequence_does_not_assume_platform(Session,monkeypatch):
    from app.routers import webhook
    from app.event_models import EventSession
    from app.models import utcnow
    from app.config import settings
    monkeypatch.setattr(settings,'cinema_mcp_enabled',True)
    outputs=[]
    async def fake_send(phone,text):outputs.append(text);return True
    async def forbidden(*a,**k):raise AssertionError('no model/provider allowed')
    monkeypatch.setattr(webhook,'send_whatsapp_message',fake_send)
    monkeypatch.setattr(webhook,'handle_cinema_whatsapp',forbidden)
    async with Session() as db:
        db.add(EventSession(id=w.session_id_for('111'),channel='cinema',updated_at=utcnow()))
        await db.commit()
        a=await webhook._events_route(db,'111','Hola busca en marketplace')
        b=await webhook._events_route(db,'111','Cuánto sale una laptop Dell')
        assert 'Cuál marketplace' in a and 'modelo o un enlace' in b
        assert all('cine' not in text.lower() and 'Facebook' not in text and 'MercadoLibre' not in text for text in outputs)
        assert 'Dell' in (await memory.get(db,'111')).last_topic
    async with Session() as db:
        assert 'Dell' in (await memory.get(db,'111')).last_topic
        assert await memory.get(db,'222') is None

async def test_explicit_yummy_keeps_previous_product_without_inventing_price(Session):
    from app import shopping_inquiry
    async with Session() as db:
        await shopping_inquiry.reply(db,'111','Hola busca en marketplace')
        await shopping_inquiry.reply(db,'111','Cuánto sale una laptop Dell')
    async with Session() as db:
        reply=await shopping_inquiry.reply(db,'111','Yummy marketplace')
        assert 'Yummy Marketplace' in reply and 'laptop Dell' in reply
        assert '$' not in reply and 'Facebook' not in reply and 'cine' not in reply.lower()
        assert 'Yummy Marketplace' in (await memory.get(db,'111')).last_topic
        assert await memory.get(db,'222') is None
