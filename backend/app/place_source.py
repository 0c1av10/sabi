"""Read an explicitly supplied restaurant website. Source facts never become tenant data."""
import asyncio
from dataclasses import dataclass
from datetime import datetime,timezone
from html.parser import HTMLParser
import ipaddress
import re
import time
import xml.etree.ElementTree as ET
import unicodedata
from urllib.parse import urlsplit,urlunsplit,urljoin,unquote
from .public_web import public_addresses,PinnedHTTPS,PublicWebError


def plain(s):return ''.join(c for c in unicodedata.normalize('NFKD',s.casefold()) if not unicodedata.combining(c))
def safe_text(s):
    text=re.sub(r'[\x00-\x1f\x7f*_`<>\u202a-\u202e\u2066-\u2069]',' ',s).strip()
    if re.search(r'https?://|@|ignore|instruccion|system|prompt|password|contrase|token|api.?key|env[ií]a|manda|forward|click|haz clic|ejecuta|descarga',plain(text)):return ''
    return text[:180]

def destination(url,host=None):
    if not isinstance(url,str) or len(url)>1800 or any(ord(c)<33 for c in url) or '\\' in url:raise PublicWebError('invalid_source')
    p=urlsplit(url)
    if p.scheme!='https' or p.port not in (None,443) or not p.hostname or p.username or p.password:raise PublicWebError('invalid_source')
    name=p.hostname.encode('idna').decode('ascii').lower()
    try:ipaddress.ip_address(name)
    except ValueError:pass
    else:raise PublicWebError('ip_source_forbidden')
    if '.' not in name or name.endswith(('.local','.internal','.localhost')):raise PublicWebError('invalid_source')
    if host and name.removeprefix('www.')!=host.removeprefix('www.'):raise PublicWebError('cross_site_source')
    path=unquote(p.path).lower()
    if any(ord(c)<32 for c in path) or '\\' in path or '..' in path or re.search(r'/(?:login|sign.?in|auth|account|admin|api|checkout|cart|orders?|reservaciones|book|pay|contact|unsubscribe|delete|remove|logout|subscribe|callback|webhook|confirm|reset|verify|cancel)(?:/|$)',path):raise PublicWebError('non_read_source')
    if p.query:raise PublicWebError('source_query_forbidden')
    return name,urlunsplit(('https',name,p.path or '/','',''))

class Page(HTMLParser):
    def __init__(self,url):super().__init__();self.url=url;self.skip=0;self.lines=[];self.links=[];self.tag='';self.title='';self.in_title=False;self.link=None
    def handle_starttag(self,tag,attrs):
        if tag in ('script','style','noscript','nav','footer'):self.skip+=1
        if tag=='title':self.in_title=True
        if tag=='a':self.link=[urljoin(self.url,dict(attrs).get('href','')),[]]
        if self.skip:return
        self.tag=tag
    def handle_endtag(self,tag):
        if tag=='title':self.in_title=False
        if tag in ('script','style','noscript','nav','footer'):self.skip=max(0,self.skip-1)
        if tag=='a' and self.link:self.links.append((self.link[0],' '.join(self.link[1])));self.link=None
    def handle_data(self,data):
        text=' '.join(data.split())
        if self.link and text:self.link[1].append(text)
        if not text or self.skip:return
        if self.in_title:self.title+=text
        self.lines.append((self.tag,text))

class Reader:
    def __init__(self):self.requests=0;self.bytes=0;self.started=time.monotonic()
    def fetch(self,url,host=None):
        name,url=destination(url,host)
        if self.requests>=6 or time.monotonic()-self.started>12:raise PublicWebError('source_budget')
        self.requests+=1;ips=public_addresses(name);c=PinnedHTTPS(name,ips[0])
        try:
            p=urlsplit(url);c.request('GET',p.path or '/',headers={'Accept':'text/html','Accept-Encoding':'identity','User-Agent':'Sabi-Source-Reader/1.0 (anonymous read-only)'})
            r=c.getresponse()
            if r.status in (301,302,303,307,308):return self.fetch(urljoin(url,r.getheader('Location','')),name)
            kind=r.getheader('Content-Type','').split(';')[0]
            if r.status!=200 or kind not in ('text/html','application/xml','text/xml'):raise PublicWebError('source_unavailable')
            if r.getheader('Content-Encoding','identity') not in ('','identity'):raise PublicWebError('encoding_rejected')
            data=r.read(500001);self.bytes+=len(data)
            if len(data)>500000 or self.bytes>1000000:raise PublicWebError('source_too_large')
            page=Page(url)
            if kind in ('application/xml','text/xml'):
                if b'<!DOCTYPE' in data.upper() or b'<!ENTITY' in data.upper():raise PublicWebError('xml_rejected')
                root=ET.fromstring(data)
                page.links=[(element.text or '',element.text or '') for element in root.iter() if element.tag.rsplit('}',1)[-1]=='loc'][:200]
            else:page.feed(data.decode('utf-8',errors='replace'))
            return page
        finally:c.close()

@dataclass(frozen=True)
class Evidence:
    status:str
    url:str=''
    name:str=''
    city:str=''
    hours:tuple[str,...]=()
    address:str=''
    menu:tuple[str,...]=()
    observed_at:str=''


def extract(page,entity,city):
    lines=page.lines;visible=' '.join(t for _,t in lines);names=' '.join([page.title]+[t for tag,t in lines if tag in ('h1','h2')])
    tokens=re.findall(r'[a-z0-9]+',plain(entity));tokens=[t for t in tokens if t not in {'restaurante','restaurant','pizzeria','local','el','la'}]
    if not tokens or not all(t in plain(names) for t in tokens):return Evidence('identity_unverified',page.url)
    if city and plain(city) not in plain(names):return Evidence('city_unverified',page.url)
    hours=[];address='';menu=[]
    for i,(tag,text) in enumerate(lines):
        if plain(text).strip() in ('horarios','horario','horario de atencion','opening hours'):
            for _,value in lines[i+1:i+9]:
                if re.search(r'\d{1,2}:\d{2}|(?:lunes|martes|miercoles|jueves|viernes|sabado|domingo)',plain(value)):
                    cleaned=safe_text(value)
                    if cleaned:hours.append(cleaned)
        if not address and re.search(r'\b(?:av\.|avenida|c\.c\.?|calle|direccion:)\s*',plain(text)) and len(text)<180:
            address=safe_text(text)
        if re.fullmatch(r'\$\s*\d+(?:[.,]\d{1,2})?',text) and i+1<len(lines):
            next_tag,next_value=lines[i+1]
            if next_tag in ('h2','h3','h4'):
                clean=safe_text(next_value)
                if clean and len(menu)<3:menu.append(clean+': '+text)
    return Evidence('ok',page.url,safe_text(entity),safe_text(city),tuple(dict.fromkeys(hours))[:6],address,tuple(menu),datetime.now(timezone.utc).isoformat())


def read_sync(url,entity,city,reader_factory=Reader):
    try:
        reader=reader_factory();page=reader.fetch(url)
        # Discover a branch via source links, then its same-host sitemap if nav is client-only.
        if city and extract(page,entity,city).status!='ok':
            links=page.links
            candidates=[(u,t) for u,t in links if plain(city) in plain(t+' '+urlsplit(u).path) and urlsplit(u).hostname==urlsplit(page.url).hostname and u!=page.url]
            if not candidates:
                try:
                    sitemap=reader.fetch(urljoin(page.url,'/sitemap.xml'),urlsplit(page.url).hostname)
                    candidates=[(u,t) for u,t in sitemap.links if plain(city) in plain(urlsplit(u).path) and urlsplit(u).hostname==urlsplit(page.url).hostname][:1]
                    if not candidates:
                        directories=[u for u,t in sitemap.links if re.search(r'/(?:ubicaciones|locations|sedes)/?$',urlsplit(u).path) and urlsplit(u).hostname==urlsplit(page.url).hostname]
                        if directories:
                            directory=reader.fetch(directories[0],urlsplit(page.url).hostname)
                            candidates=[(u,t) for u,t in directory.links if plain(city) in plain(t+' '+urlsplit(u).path) and urlsplit(u).hostname==urlsplit(page.url).hostname][:1]
                except (ValueError,OSError):candidates=[]
            for link,text in candidates[:1]:
                try:
                    destination(link,urlsplit(page.url).hostname)
                    candidate=reader.fetch(link,urlsplit(page.url).hostname)
                    verified=extract(candidate,entity,city)
                    if verified.status=='ok':return verified
                except (ValueError,OSError):pass
        return extract(page,entity,city)
    except (ValueError,OSError,TimeoutError,TypeError):return Evidence('unavailable')

async def read(url,entity,city):
    try:return await asyncio.wait_for(asyncio.to_thread(read_sync,url,entity,city),timeout=15)
    except asyncio.TimeoutError:return Evidence('unavailable')

def format_evidence(e):
    if e.status!='ok':return 'No pude vincular esa página con el local y la sede que consultaste. No usaré datos de otro restaurante. Puedes pasarme el enlace directo de la sede.'
    lines=[f'Revisé la página que compartiste para {e.name}'+(f' en {e.city}.' if e.city else '.')]
    if e.address:lines.append('Dirección publicada: '+e.address)
    if e.hours:lines.append('Horario publicado: '+'; '.join(e.hours))
    # Shared menu components can appear on every branch page. A branch heading is not menu-scope proof.
    if e.menu:lines.append('La web también muestra platos, pero no pude confirmar si el menú y sus precios corresponden a esta sede. No los presento como menú local verificado.')
    if not (e.address or e.hours or e.menu):lines.append('La página menciona el local, pero no pude extraer horario, dirección o precios con suficiente claridad.')
    lines.append('Fuente consultada ahora: '+e.url)
    lines.append('Estos datos vienen de esa web. No confirman una integración con Sabi ni disponibilidad. No hice pedidos, reservas ni contacté al local.')
    return '\n\n'.join(lines)

async def reply(db,phone,body):
    match=re.search(r'https://[^\s<>]+',body)
    if not match:return None
    from . import conversation_focus as focus
    active=await focus.get(db,phone)
    if not active or active.domain not in ('place','restaurant'):return '¿De qué local y ciudad es el enlace que quieres revisar?'
    if not active.city:return f'¿En qué ciudad queda {safe_text(active.entity)}? Así evito mezclar datos de otra sede.'
    version=active.updated_at;entity=active.entity;city=active.city
    result=await read(match[0].rstrip('.,)'),entity,city)
    current=await focus.get(db,phone)
    if not current or current.updated_at!=version or current.domain not in ('place','restaurant'):return ''
    return format_evidence(result)
