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

async def test_directory_burst_empty_answer_reaches_verified_schedules_without_more_budget(monkeypatch):
    monkeypatch.setattr(w,'local_now',lambda:datetime(2026,11,17,16,0,tzinfo=ZoneInfo('America/Caracas')))
    monkeypatch.setattr(w.settings,'cinema_max_tool_calls',4)
    calls=[];llms=[]
    async def tool(name,args,**kw):
        calls.append((name,args))
        if name=='list_providers':return {'providers':[]}
        if name=='list_cinemas':return {'provider':'cinesunidos','items':[{'id':'1019','city':'Puerto La Cruz','name':'Regina','code_status':'verified'}]}
        assert name=='get_showtimes' and args['cinema_id']=='1019' and args['city']=='Puerto La Cruz'
        return {'status':'available','next_offset':12,'items':[{'name':'PELÍCULA SIMULADA','cinema_name':'Regina','city':'Puerto La Cruz','date':'2026-11-17','starts_at':'2026-11-17T18:00:00-04:00','url':'https://example.test/movie'}]}
    async def llm(messages,tools):
        llms.append(1)
        if len(llms)>1:return {'content':[{'type':'thinking','thinking':'synthetic only'}]}
        return {'content':[{'type':'tool_use','id':str(i),'name':name,'input':args} for i,(name,args) in enumerate([('list_providers',{}),('list_cinemas',{'provider':'cinesunidos','city':'Puerto La Cruz'})]+[('list_cities',{'provider':'cinex'})]*6)]}
    monkeypatch.setattr(w,'call_tool',tool)
    text=await w.run_cinema_agent('Cines de Puerto La Cruz y Lechería',llm=llm)
    assert 'PELÍCULA SIMULADA: 18:00' in text and 'parte de la cartelera' in text
    assert len(calls)<=4 and len(llms)==2
    assert [name for name,args in calls]==['list_providers','list_cinemas','get_showtimes']

async def test_schedule_recovery_does_not_change_city_to_discovered_other_city(monkeypatch):
    calls=[]
    async def tool(name,args,**kw):
        calls.append(name)
        return {'provider':'cinesunidos','items':[{'id':'1019','city':'Caracas','name':'Otra sede','code_status':'verified'}]}
    async def llm(messages,tools):
        if len(messages)==1:return {'content':[{'type':'tool_use','id':'t','name':'list_cinemas','input':{'provider':'cinesunidos','city':'Puerto La Cruz'}}]}
        return {'content':[]}
    monkeypatch.setattr(w,'call_tool',tool)
    text=await w.run_cinema_agent('Cine Puerto La Cruz',llm=llm)
    assert text==w.UNAVAILABLE and calls==['list_cinemas']
