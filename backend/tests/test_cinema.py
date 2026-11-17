import json
import httpx
import pytest
from app import cinema_mcp as m, cinema_whatsapp as w
from app.config import settings

@pytest.fixture(autouse=True)
def clean(monkeypatch):
    m._CACHE.clear()
    monkeypatch.setattr(settings, 'cinema_mcp_enabled', True)

@pytest.mark.parametrize('name', ['get_seats','get_ticket_prices','connect_account','disconnect_account','get_concessions','get_auth_status'])
async def test_disallowed(name):
    with pytest.raises(m.CinemaUnavailable):
        await m.call_tool(name, {})

@pytest.mark.parametrize('args', [{'provider':'bogus'}, {'provider':'cinex','limit':True}, {'provider':'cinex','limit':21}, {'provider':'cinex','date':'2026-02-30'}, {'provider':'cinex','cinema_id':'directory-x'}, {'provider':'cinex','refresh':True}])
def test_invalid_args(args):
    with pytest.raises(m.CinemaUnavailable):
        m.validate_args('get_showtimes',args)

async def test_structured_sse_cached():
    calls=[]
    def h(req):
        calls.append(req)
        return httpx.Response(200,text='event: message\ndata: '+json.dumps({'id':1,'result':{'structuredContent':{'status':'available','items':[], 'partial':True, 'warnings':['incomplete']}}})+'\n\n')
    async with httpx.AsyncClient(transport=httpx.MockTransport(h)) as c:
        a=await m.call_tool('get_showtimes',{'provider':'cinex','city':'Caracas'},client=c)
        a['items'].append('mutation')
        b=await m.call_tool('get_showtimes',{'provider':'cinex','city':'Caracas'},client=c)
    assert len(calls)==1 and b['items']==[] and b['partial']
    assert json.loads(calls[0].content)['params']['arguments']['limit']==12

def test_sse_skips_notification():
    msg='data: '+json.dumps({'method':'ping'})+'\n\ndata: '+json.dumps({'id':1,'result':{'content':[{'type':'text','text':'{"items":[]}'}]}})+'\n\n'
    assert m.parse_response(msg)=={'items':[]}

async def test_size_limit():
    async with httpx.AsyncClient(transport=httpx.MockTransport(lambda req:httpx.Response(200,text='x'*256001))) as c:
        with pytest.raises(m.CinemaUnavailable):
            await m.call_tool('list_providers',{},client=c)

async def test_tool_then_answer_and_history():
    calls=[]
    async def llm(messages,tools):
        calls.append(1)
        assert 'Lechería' in messages[0]['content']
        if len(calls)==1:
            return {'content':[{'type':'tool_use','id':'t','name':'list_cinemas','input':{'provider':'cinex','city':'Lechería'}}]}
        return {'content':[{'type':'text','text':'¿Qué película te gustaría ver?'}]}
    def h(req):
        return httpx.Response(200,json={'id':1,'result':{'structuredContent':{'items':[]}}})
    async with httpx.AsyncClient(transport=httpx.MockTransport(h)) as c:
        assert await w.run_cinema_agent('algo de comedia',history=[('user','Estoy en Lechería')],client=c,llm=llm)=='¿Qué película te gustaría ver?'

async def test_total_tool_cap(monkeypatch):
    monkeypatch.setattr(settings,'cinema_max_tool_calls',2)
    hits=[];llms=[]
    async def llm(messages,tools):
        llms.append(1)
        if not tools:return {'content':[{'type':'text','text':'Consulta lista.'}]}
        return {'content':[{'type':'tool_use','id':str(i),'name':'list_cities','input':{'provider':'cinex','offset':len(llms)*10+i}} for i in range(3)]}
    def h(req):
        hits.append(1);return httpx.Response(200,json={'id':1,'result':{'structuredContent':{'items':[]}}})
    async with httpx.AsyncClient(transport=httpx.MockTransport(h)) as c:
        assert await w.run_cinema_agent('cine',client=c,llm=llm)=='Consulta lista.'
    assert len(hits)==2 and len(llms)==2

async def test_no_account_tool_network():
    calls=[]
    async def llm(messages,tools):
        calls.append(1)
        if len(calls)==1:return {'content':[{'type':'tool_use','id':'a','name':'get_seats','input':{}}]}
        assert 'query_unavailable' in messages[-1]['content'][0]['content']
        return {'content':[{'type':'text','text':'Elige en la web oficial.'}]}
    def h(req):raise AssertionError('not called')
    async with httpx.AsyncClient(transport=httpx.MockTransport(h)) as c:
        assert await w.run_cinema_agent('asientos',client=c,llm=llm)=='Elige en la web oficial.'

async def test_feature_off(monkeypatch):
    monkeypatch.setattr(settings,'cinema_mcp_enabled',False)
    assert not await w.wants_cinema(None,'123','cine')

async def test_router_cinema_context(monkeypatch):
    async def no(*args):return None
    monkeypatch.setattr(w,'restaurant_by_mention',no)
    class DB:
        async def get(self,model,*args):return type('Session',(),{'updated_at':w.utcnow()})() if model.__name__=='EventSession' else None
    assert await w.wants_cinema(DB(),'123','¿y mañana?')
    assert not await w.wants_cinema(DB(),'123','[sabi:bizza] pizza')
    assert not await w.wants_cinema(DB(),'123','hola')

async def test_explicit_cinema_beats_old_gym_context(monkeypatch):
    from app.routers import webhook
    seen=[]
    async def no_memory(*a,**k):pass
    async def yes(*a,**k):return True
    async def reply(*a,**k):seen.append('cinema');return 'cine'
    async def gym(*a,**k):raise AssertionError('gym must not capture explicit cinema')
    monkeypatch.setattr(webhook.memory,'note',no_memory)
    monkeypatch.setattr(webhook,'wants_cinema',yes)
    monkeypatch.setattr(webhook,'handle_cinema_whatsapp',reply)
    monkeypatch.setattr(webhook.gym_whatsapp,'wants_gym',gym)
    assert await webhook._events_route(None,'123','quiero ir al cine')=='cine'
    assert seen==['cinema']

@pytest.mark.parametrize('hour',[0,2,3])
async def test_midnight_relative_date_no_model(hour,monkeypatch):
    from datetime import datetime
    from zoneinfo import ZoneInfo
    monkeypatch.setattr(w,'local_now',lambda:datetime(2026,11,17,hour,0,tzinfo=ZoneInfo('America/Caracas')))
    async def llm(*a):raise AssertionError('no model before day is resolved')
    assert await w.run_cinema_agent('¿qué películas hay mañana?',llm=llm)=='Para ubicar el día: ¿te refieres al martes 17/11 o al miércoles 18/11?'

@pytest.mark.parametrize('text',['hoy 2026-11-18','mañana 18 de noviembre'])
def test_explicit_date_not_reasked(text):
    from datetime import datetime
    assert w.midnight_question(text,datetime(2026,11,17,2,0)) is None

def test_after_four_not_ambiguous():
    from datetime import datetime
    assert w.midnight_question('hoy',datetime(2026,11,17,4,0)) is None

@pytest.mark.parametrize('body',['quiero un concierto','quiero comer pizza','quiero ir a boxeo','hola','[sabi:eventos] entradas'])
async def test_exit_cinema_context(body,monkeypatch):
    async def no(*args):return None
    monkeypatch.setattr(w,'restaurant_by_mention',no)
    class DB:
        async def get(self,model,*args):return type('Session',(),{'updated_at':w.utcnow()})() if model.__name__=='EventSession' else None
    assert not await w.wants_cinema(DB(),'123',body)

async def test_merchant_name_wins_over_cinema(monkeypatch):
    async def restaurant(*args):return object()
    monkeypatch.setattr(w,'restaurant_by_mention',restaurant)
    assert not await w.wants_cinema(None,'123','pizza en Bizza antes del cine')
