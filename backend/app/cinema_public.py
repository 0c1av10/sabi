"""Narrow fallback for the official Plaza Mayor page when Cinve cannot resolve its code.

No scripts run, no checkout is opened, no venue IDs are invented. Public HTML only.
"""
import re
from datetime import datetime, timedelta
from html.parser import HTMLParser
from zoneinfo import ZoneInfo
import httpx

URL = 'https://www.cinex.com.ve/cinex-plazamayor.html'
MONTHS = ('enero','febrero','marzo','abril','mayo','junio','julio','agosto','septiembre','octubre','noviembre','diciembre')

class Node:
    def __init__(self,tag='',attrs=(),parent=None):
        self.tag,self.attrs,self.parent,self.children=tag,dict(attrs),parent,[]
    def text(self):
        return ' '.join(c if isinstance(c,str) else c.text() for c in self.children)
    def all(self,test):
        for c in self.children:
            if isinstance(c,Node):
                if test(c):yield c
                yield from c.all(test)
    def cls(self,name):return name in self.attrs.get('class','').split()

class Tree(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True);self.root=Node();self.current=self.root
    def handle_starttag(self,tag,attrs):
        n=Node(tag,attrs,self.current);self.current.children.append(n)
        if tag not in ('img','br','hr','input','meta','link','source','wbr','area','base','embed','param','track'):
            self.current=n
    def handle_endtag(self,tag):
        n=self.current
        while n.parent:
            if n.tag==tag:self.current=n.parent;return
            n=n.parent
    def handle_data(self,data):self.current.children.append(data)


def parse_plaza_html(html: str, *, now=None, requested_date=None, query='') -> dict:
    now=now or datetime.now(ZoneInfo('America/Caracas'))
    requested_date=requested_date or now.date().isoformat()
    p=Tree();p.feed(html);root=p.root
    titles=list(root.all(lambda n:n.tag=='h3' and n.cls('title')))
    if not titles or ' '.join(titles[0].text().upper().split())!='PLAZA MAYOR':
        raise ValueError('venue identity not confirmed')
    # The page must explicitly identify city and ISO current date, not a soft404.
    if 'Lechería' not in html or now.date().isoformat() not in html:
        raise ValueError('page freshness not established')
    labels={}
    for n in root.all(lambda n:bool(re.fullmatch(r'divdate\d+',n.attrs.get('id','')))):
        text=n.text().lower();m=re.search(r'\b(\d{1,2})\b',text)
        month=next((i+1 for i,x in enumerate(MONTHS) if x in text),None)
        if not m or not month:continue
        # Resolve year only within the next366 days, so year rollover is explicit.
        for delta in range(367):
            d=now.date()+timedelta(days=delta)
            if d.day==int(m[1]) and d.month==month:
                labels[n.attrs['id'][7:]]=d.isoformat();break
    items=[]
    for page in root.all(lambda n:bool(re.fullmatch(r'pagedate\d+',n.attrs.get('id','')))):
        d=labels.get(page.attrs['id'][8:])
        if d!=requested_date:continue
        for movie in page.all(lambda n:n.cls('celeb-container')):
            title=next(movie.all(lambda n:n.tag=='h5' and n.cls('title')),None)
            if title is None:continue
            name=' '.join(title.text().split())
            if query and query.casefold() not in name.casefold():continue
            genre=next(movie.all(lambda n:n.cls('movieinforow1')),None)
            for slot in movie.all(lambda n:n.cls('cinemasessionpos')):
                text=' '.join(slot.text().split());m=re.search(r'\b(\d{1,2}):(\d{2})\s*(am|pm)\b',text,re.I)
                if not m:continue
                hour=int(m[1])%12+(12 if m[3].lower()=='pm' else 0)
                starts=datetime.fromisoformat(f'{d}T{hour:02}:{m[2]}:00-04:00')
                if starts<=now:continue
                boxoffice='solo por taquilla' in slot.attrs.get('title','').lower()
                items.append({'kind':'showtime','name':name,'genre':genre.text().split(':',1)[-1].strip() if genre else '',
                    'cinema_name':'Cinex Plaza Mayor','city':'Lechería','date':d,'time':starts.strftime('%H:%M'),
                    'starts_at':starts.isoformat(),'sales_channel':'box_office_only' if boxoffice else 'not_verified','url':URL})
    if requested_date not in labels.values():raise ValueError('requested date not published')
    return {'provider':'cinex','status':'available','queried_at':now.isoformat(),'timezone':'America/Caracas',
        'sources':[{'url':URL,'fetched_at':now.isoformat(),'cached':False}],'partial':False,
        'warnings':['Funciones marcadas sólo por taquilla no se pueden comprar desde aquí.'],
        'total':len(items),'items':items[:20],'source_type':'official_html_fallback'}


async def read_plaza(*, requested_date=None,query='',client=None):
    own=client is None;client=client or httpx.AsyncClient(timeout=12,follow_redirects=False)
    try:
        async with client.stream('GET',URL) as r:
            r.raise_for_status();chunks=[];size=0
            async for chunk in r.aiter_bytes():
                size+=len(chunk)
                if size>2500000:raise ValueError('page too large')
                chunks.append(chunk)
        return parse_plaza_html(b''.join(chunks).decode('utf-8'),requested_date=requested_date,query=query)
    finally:
        if own:await client.aclose()
