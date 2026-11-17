import json
from types import SimpleNamespace
import asyncio
import pytest
from app import product_search as p,shopping_inquiry as shopping,conversation_focus as focus

ID='6acfb8365935ab05a39afee2'
def response(data,status=200):return SimpleNamespace(body=json.dumps({'error':None,'body':data}).encode(),status=status,content_type='application/json',observed_at='2026-11-17T08:00:00Z')
class Reader:
    calls=[]
    def __init__(self,site,query,**kwargs):self.calls=[];self.query=query;assert site=='yummy';assert kwargs['max_requests']==4
    def fetch(self,url,method='GET',body=None):
        self.calls.append((url,method,body))
        if method=='POST':
            assert json.loads(body)=={'query':'laptop dell'}
            return response({'hits':[{'objectID':ID,'title':'Laptop Dell 3380','price':1,'inStock':True},{'objectID':'bad','title':'Laptop Dell 3380','price':9,'inStock':True},{'objectID':ID,'title':'Laptop Dell 3380','price':9,'inStock':True}]})
        assert url=='https://api.yummy-marketplace.com/post/v2/'+ID
        return response({'post':{'_id':ID,'title':'Laptop Dell 3380','price':209,'active':True,'paused':False}})

def test_real_shape_search_detail_price_and_query():
    r=p.search_yummy_sync('Cuánto sale una laptop Dell',Reader)
    assert r.status=='ok' and len(r.products)==1
    assert r.products[0].price=='209' and r.products[0].url.endswith(ID)
    text=p.format_result(r,'laptop dell')
    assert '$209' in text and 'USD' not in text and 'No he comprado' in text

def test_reject_inactive_or_mismatched_product():
    class Mismatch(Reader):
        def fetch(self,url,*args):
            r=super().fetch(url,*args)
            if '/post/v2/' in url:return response({'post':{'_id':'other','title':'Laptop Dell','price':209,'active':True,'paused':False}})
            return r
    assert not p.search_yummy_sync('laptop dell',Mismatch).products

def test_stop_on_access_denial_without_retry():
    class Denied(Reader):
        def fetch(self,*args):return response({},429)
    assert p.search_yummy_sync('laptop dell',Denied).status=='unavailable'

@pytest.mark.parametrize('price',[None,'NaN','Infinity',-1,0,True,'<script>'])
def test_bad_prices_not_rendered(price):assert p.price_of(price) is None

def test_no_seller_instructions_or_raw_errors():
    text=p.format_result(p.SearchResult((),'', 'unavailable'),'x')
    assert 'verificar' in text
    assert p.label('Dell\n*SALE*<x>')=='Dell  SALE  x'

async def test_dialog_yummy_dell_durable_context_and_new_query(Session,monkeypatch):
    seen=[]
    async def search(query):
        seen.append(query)
        return p.SearchResult((p.Product('Laptop Dell3380','209','https://yummy-marketplace.com/producto/'+ID,'now'),),'','ok')
    monkeypatch.setattr(p,'search_yummy',search)
    async with Session() as db:
        await shopping.reply(db,'111','busca en marketplace')
        await shopping.reply(db,'111','Cuánto sale una laptop Dell')
    async with Session() as db:
        text=await shopping.reply(db,'111','Yummy marketplace')
        assert '$209' in text and seen==['laptop dell']
        assert (await focus.get(db,'111')).platform=='Yummy Marketplace'
        assert await focus.get(db,'222') is None

async def test_shopping_old_result_suppressed_after_reset(Session,monkeypatch):
    started=asyncio.Event();resume=asyncio.Event()
    async def search(query):started.set();await resume.wait();return p.SearchResult((),'', 'unavailable')
    monkeypatch.setattr(p,'search_yummy',search)
    async with Session() as db:await focus.save(db,'111',domain='shopping',entity='Laptop Dell',platform='Yummy Marketplace')
    async def first():
        async with Session() as db:return await shopping.reply(db,'111','Yummy marketplace')
    task=asyncio.create_task(first());await started.wait()
    async with Session() as db:await focus.forget(db,'111')
    resume.set();assert await task==''

async def test_generic_explicit_yummy_search_and_rides_not_stolen(Session,monkeypatch):
    seen=[]
    async def search(query):seen.append(query);return p.SearchResult((),'', 'no_verified_matches')
    monkeypatch.setattr(p,'search_yummy',search)
    async with Session() as db:
        text=await shopping.reply(db,'111','busca cafetera en Yummy Marketplace')
        assert seen==['cafetera'] and 'no prueba que no existan' in text
        assert await shopping.reply(db,'111','Cuánto cuesta el taxi en Yummy') is None
