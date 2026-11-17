from datetime import datetime
import pytest
from app.cinema_public import parse_plaza_html

HTML='''<html lang="es-VE"><h3 class="title">PLAZA MAYOR</h3><p>Lechería 2026-11-17</p><div id="divdate0">Martes 17 Noviembre</div><div id="divdate1">Miercoles 18 Noviembre</div><div id="pagedate0"><div class="celeb-container"><h5 class="title">YO SOY ROCKY</h5><div class="movieinforow1">Genero: Drama</div><div class="cinemasessionpos" title="Función venta solo por taquilla"><button>02<br/>06:40 pm</button></div></div></div><div id="pagedate1"><div class="celeb-container"><h5 class="title">OTRA PELÍCULA</h5><div class="cinemasessionpos" title="Función venta solo por taquilla"><button>03<br/>05:00 pm</button></div></div></div></html>'''
NOW=datetime.fromisoformat('2026-11-17T03:00:00-04:00')

def test_boxoffice_without_code():
    x=parse_plaza_html(HTML,now=NOW,requested_date='2026-11-17')
    assert x['total']==1 and x['items'][0]['name']=='YO SOY ROCKY'
    assert x['items'][0]['time']=='18:40' and x['items'][0]['sales_channel']=='box_office_only'
    assert 'cinema_id' not in x['items'][0]

def test_wrong_day_not_mixed():
    x=parse_plaza_html(HTML,now=NOW,requested_date='2026-11-18')
    assert x['items'][0]['name']=='OTRA PELÍCULA'

def test_past_time_excluded():
    assert not parse_plaza_html(HTML,now=NOW.replace(hour=20))['items']

@pytest.mark.parametrize('html',[HTML.replace('PLAZA MAYOR','SAN IGNACIO'),HTML.replace('2026-11-17','2026-11-16'),'<h3>not found</h3>'])
def test_identity_and_freshness(html):
    with pytest.raises(ValueError):parse_plaza_html(html,now=NOW)

def test_unknown_date_fails_closed():
    with pytest.raises(ValueError):parse_plaza_html(HTML,now=NOW,requested_date='2026-11-19')

@pytest.mark.asyncio
async def test_agent_attaches_official_fallback(monkeypatch):
    from app import cinema_whatsapp as w
    calls=[]
    async def tool(name,args,client=None):
        return {'partial':True,'status':'unavailable','items':[]}
    async def official(**kw):
        calls.append(kw)
        return parse_plaza_html(HTML,now=NOW,requested_date=kw['requested_date'])
    async def model(messages,tools):
        if len(messages)==1:
            return {'content':[{'type':'tool_use','id':'read1','name':'list_cinemas','input':{'provider':'cinex','query':'Plaza Mayor','city':'Lechería'}}]}
        import json
        result=json.loads(messages[-1]['content'][0]['content'])
        assert result['official_plaza_mayor_showtimes']['items'][0]['name']=='YO SOY ROCKY'
        return {'content':[{'type':'text','text':'Respuesta de prueba, no generada por modelo.'}]}
    monkeypatch.setattr(w,'call_tool',tool);monkeypatch.setattr(w,'read_plaza',official)
    x=await w.run_cinema_agent('Cartelera Plaza Mayor Lechería 2026-11-17',llm=model)
    assert x=='Respuesta de prueba, no generada por modelo.' and len(calls)==1
    assert calls[0]['requested_date']=='2026-11-17'

@pytest.mark.asyncio
async def test_no_fallback_other_venue(monkeypatch):
    from app import cinema_whatsapp as w
    async def tool(name,args,client=None):return {'partial':True,'items':[]}
    async def no_read(**kw):raise AssertionError('wrong venue')
    async def model(messages,tools):
        if len(messages)==1:return {'content':[{'type':'tool_use','id':'read1','name':'list_cinemas','input':{'provider':'cinex','query':'San Ignacio'}}]}
        return {'content':[{'type':'text','text':'prueba'}]}
    monkeypatch.setattr(w,'call_tool',tool);monkeypatch.setattr(w,'read_plaza',no_read)
    assert await w.run_cinema_agent('Cine San Ignacio 2026-11-17',llm=model)=='prueba'
