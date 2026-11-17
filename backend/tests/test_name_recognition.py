import pytest
from app import memory

@pytest.mark.parametrize('text',[
    'Dime entonces del cine Regina de puerto la cruz','Soy entonces del cine',
    'Llámame mañana','Llámame luego','Llámame hoy por la tarde',
    'Soy alérgico al maní','Soy vegetariana','Soy de Lechería','Soy cliente de Nacional',
    'Soy estudiante de computación','Soy buscando algo de comer','Soy nuevo en esto',
    'Me llamo la atención el menú','Soy Ana tengo hambre','Soy Ana Pérez del restaurante',
    'Me llamo Ana quiero pedir pizza',
])
def test_non_introductions_not_saved(text):
    # An explicit new intent after the name is handled separately below.
    if text=='Me llamo Ana quiero pedir pizza':assert memory.extract_name(text)=='Ana'
    else:assert memory.extract_name(text)==''

@pytest.mark.parametrize('text,expected',[
    ('Me llamo Ana','Ana'),('Mi nombre es Octavio Caamaño','Octavio Caamaño'),
    ('Hola soy Maria y quiero una clase','Maria'),('Soy Ana, quiero pedir','Ana'),
    ('Llámame Luis','Luis'),('Me llamo Ana para pedir','Ana'),
])
def test_clear_introductions(text,expected):assert memory.extract_name(text)==expected

async def test_no_overwrite_explicit_name_and_profile_is_only_fallback(Session):
    async with Session() as db:
        await memory.note(db,'111','Me llamo Ana',profile_name='Perfil Uno')
        await memory.note(db,'222','',profile_name='Perfil Dos')
    async with Session() as db:
        for text in ['Dime entonces del cine','Llámame mañana','Soy alérgico al maní']:
            await memory.note(db,'111',text,profile_name='Otra Cosa')
        a=await memory.get(db,'111');b=await memory.get(db,'222')
        assert (a.name,a.name_source)==('Ana','user')
        assert (b.name,b.name_source)==('Perfil Dos','profile')
        await memory.note(db,'222','Me llamo Luis',profile_name='Perfil Dos')
    async with Session() as db:
        assert (await memory.get(db,'222')).name=='Luis'
        assert (await memory.get(db,'111')).name=='Ana'

async def test_legacy_name_is_not_silently_repaired(Session):
    async with Session() as db:
        await memory.set_name(db,'111','Entonces')
        await memory.note(db,'111','Hola',profile_name='Octavio')
        assert (await memory.get(db,'111')).name=='Entonces'
