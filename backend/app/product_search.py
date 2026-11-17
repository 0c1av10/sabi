"""Bounded anonymous catalog reads. No model, account, basket or payment calls."""
import asyncio
from dataclasses import dataclass
from decimal import Decimal,InvalidOperation
import json
import re
import unicodedata
from urllib.parse import urlencode
from .public_web import PublicReader,PublicWebError

STOP={'cuanto','sale','cuesta','cuestan','precio','precios','una','un','unos','unas','de','del','el','la','las','los','en','por','para','favor','quiero','busca','buscame','buscar','necesito','comprar','consigueme','yummy','marketplace','me','dime','tienes','tienen','que','puedes','conseguir'}
def plain(s):
    return ''.join(c for c in unicodedata.normalize('NFKD',s.lower()) if not unicodedata.combining(c))
def query_for(s):
    return ' '.join(t for t in re.findall(r'[a-z0-9]+',plain(s)) if t not in STOP)[:80].strip()
def label(s):
    return re.sub(r'[\x00-\x1f\x7f*_\[\]`<>\u202a-\u202e\u2066-\u2069]',' ',str(s))[:120].strip()
def price_of(value):
    if isinstance(value,bool):return None
    try:
        n=Decimal(str(value))
        return format(n.normalize(),'f') if n.is_finite() and 0<n<100000000 else None
    except InvalidOperation:return None

@dataclass(frozen=True)
class Product:
    title:str
    price:str
    url:str
    observed_at:str

@dataclass(frozen=True)
class SearchResult:
    products:tuple[Product,...]
    url:str
    status:str
    observed_at:str=''

def _json(response):
    if response.status in (401,403,429):raise PublicWebError('source_unavailable')
    if response.status!=200 or response.content_type!='application/json':raise PublicWebError('unverified_response')
    value=json.loads(response.body)
    if value.get('error') is not None:raise PublicWebError('source_error')
    return value.get('body',{})

def search_yummy_sync(query,reader_factory=PublicReader):
    query=query_for(query)
    if not query:return SearchResult((),'','missing_query')
    source='https://yummy-marketplace.com/productos?'+urlencode({'q':query})
    reader=reader_factory('yummy',query,max_requests=4,max_total_bytes=1000000)
    try:
        response=reader.fetch('https://api.yummy-marketplace.com/search/v1/posts','POST',json.dumps({'query':query}))
        data=_json(response);hits=data.get('hits',[])
        if not isinstance(hits,list):raise PublicWebError('invalid_hits')
        products=[];seen=set();tokens=query.split()
        # At most three source details, no discovery loop, redirects or other sites.
        candidates=[]
        for hit in hits[:12]:
            if not isinstance(hit,dict):continue
            title=plain(str(hit.get('title','')))
            if all(t in title for t in tokens) and hit.get('inStock') is True:candidates.append(hit)
        for hit in candidates[:3]:
            identifier=hit.get('objectID','')
            if not isinstance(identifier,str) or not re.fullmatch('[a-f0-9]{24}',identifier) or identifier in seen:continue
            seen.add(identifier)
            detail_response=reader.fetch('https://api.yummy-marketplace.com/post/v2/'+identifier)
            detail=_json(detail_response).get('post',{})
            if detail.get('_id')!=identifier or detail.get('active') is not True or detail.get('paused') is not False:continue
            title=label(detail.get('title',''));price=price_of(detail.get('price'))
            if not title or not price or not all(t in plain(title) for t in tokens):continue
            # Known site route verified against the live frontend. Never accept a destination from seller content.
            products.append(Product(title,price,'https://yummy-marketplace.com/producto/'+identifier,detail_response.observed_at))
        return SearchResult(tuple(products),source,'ok' if products else 'no_verified_matches',response.observed_at)
    except (PublicWebError,TimeoutError,OSError,ValueError,TypeError,AttributeError):
        # Never pass raw source content or errors to the conversation or model.
        return SearchResult((),source,'unavailable')

async def search_yummy(query):
    try:return await asyncio.wait_for(asyncio.to_thread(search_yummy_sync,query),timeout=16)
    except asyncio.TimeoutError:return SearchResult((),'','unavailable')

def format_result(result,query):
    if result.status=='missing_query':return '¿Qué producto buscas en Yummy Marketplace?'
    if result.status=='unavailable':return 'No pude verificar el catálogo de Yummy Marketplace ahora. No te voy a dar precios sin comprobar. Podemos seguir con un enlace de producto.'
    if not result.products:return f'No encontré publicaciones verificables para {label(query)} en esta consulta de Yummy Marketplace. Eso no prueba que no existan.'
    lines=[f'En Yummy Marketplace encontré estas publicaciones para {label(query)}:']
    for p in result.products:lines.append(f'{p.title}: ${p.price}\n{p.url}')
    # UI uses "$" without an ISO currency code. Do not silently assert USD or final checkout total.
    lines.append('Precios con el símbolo $ que muestra el sitio, consultados ahora. Son publicaciones, no stock garantizado ni total con envío. No he comprado ni reservado nada.')
    return '\n\n'.join(lines)
