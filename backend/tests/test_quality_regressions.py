import pytest
from app import memory,concierge,cinema_whatsapp as w
from app.models import Restaurant

def test_real_name_contamination_no_model():
    assert memory.extract_name('Dime entonces del cine Regina de puerto la cruz')==''
    assert memory.extract_name('Me llamo Ana')=='Ana'
    assert memory.first_name('Entonces')==''

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
