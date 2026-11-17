from datetime import datetime,timedelta
import pytest
from app.cinema_snapshot import store_snapshot,read_snapshot
N=datetime.fromisoformat('2026-11-17T03:31:43-04:00')
def payload():return {'status':'available','partial':False,'total':1,'next_offset':None,'sources':[{'url':'https://www.cinex.com.ve/cinex-plazamayor.html','fetched_at':N.isoformat(),'cached':False}],'items':[{'date':'2026-11-17','cinema_name':'Cinex Plaza Mayor','name':'Título de prueba','time':'18:40','starts_at':'2026-11-17T18:40:00-04:00','sales_channel':'box_office_only'}]}
KW={'provider':'cinex','venue_key':'plaza-mayor','venue_name':'Cinex Plaza Mayor','city':'Lechería','show_date':'2026-11-17'}

async def test_roundtrip_durable_and_markdown(Session):
    async with Session() as db:
        row=await store_snapshot(db,payload(),**KW,now=N);assert '| Título de prueba | 18:40 | Sólo taquilla |' in row.markdown;await db.commit()
    async with Session() as db:
        x=await read_snapshot(db,provider='cinex',venue_key='plaza-mayor',show_date='2026-11-17',now=N+timedelta(hours=1));assert x['total']==1
        assert await read_snapshot(db,provider='cinex',venue_key='plaza-mayor',show_date='2026-11-17',now=N+timedelta(days=1)) is None

async def test_past_hours_filtered(Session):
    async with Session() as db:
        await store_snapshot(db,payload(),**KW,now=N)
        x=await read_snapshot(db,provider='cinex',venue_key='plaza-mayor',show_date='2026-11-17',now=N.replace(hour=20));assert x['total']==0

@pytest.mark.parametrize('bad',['partial','wrongday','wrongvenue','missingpage','stale'])
async def test_failures_do_not_replace_good_data(Session,bad):
    async with Session() as db:
        await store_snapshot(db,payload(),**KW,now=N);p=payload()
        if bad=='partial':p['partial']=True
        if bad=='wrongday':p['items'][0]['date']='2026-11-18'
        if bad=='wrongvenue':p['items'][0]['cinema_name']='Otro cine'
        if bad=='missingpage':p['total']=2
        if bad=='stale':p['sources'][0]['fetched_at']=(N-timedelta(days=2)).isoformat()
        with pytest.raises(ValueError):await store_snapshot(db,p,**KW,now=N)
        assert (await read_snapshot(db,provider='cinex',venue_key='plaza-mayor',show_date='2026-11-17',now=N))['total']==1

async def test_read_first_avoids_second_provider_call(Session):
    from app.cinema_snapshot import snapshot_first
    calls=[]
    async def loader():calls.append(1);return payload()
    async with Session() as db:
        for _ in range(2):
            x=await snapshot_first(db,loader=loader,**KW,now=N);assert x['total']==1
    assert len(calls)==1
