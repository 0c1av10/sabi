from datetime import datetime
from zoneinfo import ZoneInfo
import pytest
from app import cinema_whatsapp as w
DATA={'status':'available','partial':False,'next_offset':12,'items':[{'name':'COMEDIA DE PRUEBA','cinema_name':'Supercines Puente Real','date':'2026-11-17','time':'17:00','starts_at':'2026-11-17T17:00:00-04:00','url':'https://supercines.com.ve/cines'}]}

@pytest.mark.parametrize('failure',['empty','exception','thinking'])
async def test_successful_read_survives_synthesis_failure(monkeypatch,failure):
    monkeypatch.setattr(w,'local_now',lambda:datetime(2026,11,17,3,0,tzinfo=ZoneInfo('America/Caracas')))
    async def tool(*a,**kw):return DATA
    async def llm(messages,tools):
        if len(messages)==1:return {'content':[{'type':'tool_use','name':'get_showtimes','id':'t','input':{'provider':'supercines','cinema_id':'3'}}]}
        if failure=='exception':raise ValueError('synthetic')
        return {'content':[{'type':'thinking','thinking':'synthetic'}]} if failure=='thinking' else {'content':[]}
    monkeypatch.setattr(w,'call_tool',tool)
    x=await w.run_cinema_agent('Supercines Barcelona',llm=llm)
    assert 'COMEDIA DE PRUEBA: 17:00' in x and '2026-11-17' in x and 'parte de la cartelera' in x
    assert 'en un rato' not in x and 'No pude' not in x

def test_wrong_date_and_past_never_used(monkeypatch):
    monkeypatch.setattr(w,'local_now',lambda:datetime(2026,11,18,3,0,tzinfo=ZoneInfo('America/Caracas')))
    assert not w.verified_answer([DATA])
