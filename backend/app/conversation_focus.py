"""Per-user, 30-minute explicit task state. No inferred tastes or external search."""
import re
from datetime import datetime,timedelta
from sqlalchemy import String,DateTime,select,delete
from sqlalchemy.orm import Mapped,mapped_column
from .models import Base,utcnow
from .whatsapp import digits

class ConversationFocus(Base):
    __tablename__='conversation_focus'
    phone:Mapped[str]=mapped_column(String(30),primary_key=True)
    domain:Mapped[str]=mapped_column(String(30),default='general')
    entity:Mapped[str]=mapped_column(String(100),default='')
    city:Mapped[str]=mapped_column(String(100),default='')
    platform:Mapped[str]=mapped_column(String(80),default='')
    updated_at:Mapped[datetime]=mapped_column(DateTime)
    expires_at:Mapped[datetime]=mapped_column(DateTime)

async def get(db,phone,now=None):
    now=now or utcnow()
    row=(await db.execute(select(ConversationFocus).where(ConversationFocus.phone==digits(phone),ConversationFocus.expires_at>now).execution_options(populate_existing=True))).scalar_one_or_none()
    from .auth import response_format_request
    if row and row.domain in ('place','restaurant') and response_format_request(row.entity+' en '+row.city):return None
    return row

async def save(db,phone,*,domain,entity='',city='',platform='',now=None):
    now=now or utcnow()
    values=dict(phone=digits(phone),domain=domain[:30],entity=entity[:100],city=city[:100],platform=platform[:80],updated_at=now,expires_at=now+timedelta(minutes=30))
    if not values['phone']:raise ValueError('phone required')
    dialect=db.bind.dialect.name
    if dialect=='postgresql':from sqlalchemy.dialects.postgresql import insert
    elif dialect=='sqlite':from sqlalchemy.dialects.sqlite import insert
    else:raise ValueError('unsupported atomic focus store')
    statement=insert(ConversationFocus).values(**values)
    statement=statement.on_conflict_do_update(index_elements=['phone'],set_={k:v for k,v in values.items() if k!='phone'},where=ConversationFocus.updated_at<=now)
    await db.execute(statement);await db.commit()
    return await get(db,phone,now=now)

async def forget(db,phone):
    await db.execute(delete(ConversationFocus).where(ConversationFocus.phone==digits(phone)));await db.commit()

ENTITY=re.compile(r'^(?:sabes? (?:que|qué) es|conoces|busca(?:me)? (?:el |la )?(?:restaurante|pizzer[ií]a))\s+(.+?)\??$',re.I)

async def place_reply(db,phone,body):
    from . import concierge
    text=concierge._plain(body).strip(' ¿?!.')
    match=ENTITY.match(body.strip())
    if match:
        previous=await get(db,phone)
        city=previous.city if previous and previous.domain in ('place','restaurant') and (not previous.entity or concierge._plain(previous.entity)==concierge._plain(match[1])) else ''
        await save(db,phone,domain='place',entity=match[1],city=city)
        return f'Mantengo la consulta de {match[1]} en {city}.' if city else f'¿En qué ciudad queda {match[1]}?'
    if not (re.search(r'\b(pizzeria|restaurante|local)\b',text) or text in ('buscala','buscalo','busca')):return None
    focus=await get(db,phone)
    if not focus or focus.domain not in ('place','restaurant'):return None
    if re.search(r'\b(pizzeria|restaurante|local)\b',text):
        from .auth import restaurant_by_mention
        # A catalog business named here ("quiero pedir en NACIONAL Restaurante") is an order, not a place hint.
        if await restaurant_by_mention(db,body):return None
        # Only explicit city patterns, never GPS or guessed neighboring city.
        citymatch=re.search(r'\ben\s+([a-záéíóúñ ]+?)(?:\s+en la |\s+por |$)',body,re.I)
        city=citymatch[1].strip().title() if citymatch else focus.city
        await save(db,phone,domain='restaurant',entity=focus.entity,city=city)
        return f'Entendido: {focus.entity}'+(f' en {city}.' if city else '. ¿En qué ciudad queda?')
    if text in ('buscala','buscalo','busca'):
        if not focus.city:return f'¿En qué ciudad queda {focus.entity}?'
        return f'Mantengo la consulta de {focus.entity} en {focus.city}. La búsqueda web de locales aún no está conectada; no tengo una fuente nueva para darte datos verificados.'
    return None


def declared_city(body):
    """An explicit task-location statement, never a GPS or residence inference."""
    from .auth import response_format_request
    if response_format_request(body):return ''
    text=body.strip().strip(' ¿?!.')
    match=re.fullmatch(r'(?:estoy en|busca en|buscame en|mejor en|ahora en|cambia (?:a|para)|en)\s+([A-Za-zÁÉÍÓÚÑÜáéíóúñü ]{2,80})',text,re.I)
    if not match:return ''
    value=match[1].strip()
    from .concierge import _plain
    from .venezuela import canonical, find_city
    # A known city ("Puerto La Cruz") is a city even when it contains a stop word.
    if find_city(value):return canonical(value)
    if len(value.split())>4 or re.search(r'\b(mensajes?|partes?|lineas?|palabras?|tabla|lista|resumen|detalle|ingles|espanol|pizzas?|restaurante|local|delivery|pedido|mi|la|el|casa|trabajo|oficina|tres|dos|mejor)\b',_plain(value)):return ''
    return value

_BARE_ANSWER=re.compile(r"^[A-Za-zÁÉÍÓÚÑÜáéíóúñü]{2,30}(?:\s+[A-Za-zÁÉÍÓÚÑÜáéíóúñü]{2,30}){0,2}$")
_BARE_NOT_CITY={'nada','no se','nose','buscala','buscalo','busca','ninguna','ninguno','da igual',
                'menu','el menu','carta','la carta','precio','precios','horario','horarios',
                'delivery','retiro','pedido','gracias','ok','vale','dale'}


async def pending_city_answer(db,phone,body):
    """After Sabi asked "¿En qué ciudad queda X?" for an unresolved place, a bare short
    reply ("Lecheria") is the answer to that question, never a new query. A restaurant
    mention, a food word or a greeting is left for the normal routes."""
    active=await get(db,phone)
    if not(active and active.domain=='place' and active.entity and not active.city):return ''
    candidate=body.strip().strip(' ¿?!.,')
    from . import concierge
    from .auth import restaurant_by_mention
    text=concierge._plain(candidate)
    if not _BARE_ANSWER.fullmatch(candidate) or text in _BARE_NOT_CITY:return ''
    if concierge.is_greeting(candidate) or concierge.wants_food(candidate):return ''
    if await restaurant_by_mention(db,candidate):return ''
    from .venezuela import canonical
    return canonical(candidate.title())


async def city_reply(db,phone,body):
    city=declared_city(body) or await pending_city_answer(db,phone,body)
    if not city:return None
    active=await get(db,phone)
    if active and active.domain in ('shopping','cinema','gym','events'):
        # Remember the new task city, but do not falsely claim geographic filtering.
        await save(db,phone,domain=active.domain,entity=active.entity,platform=active.platform,city=city)
        return 'Entendí la ciudad que indicas: '+city+'. Este tipo de búsqueda todavía no tiene un filtro geográfico verificado; no voy a presentar resultados de otra ciudad como si fueran locales.'
    if active and active.domain in ('place','restaurant'):
        from .concierge import _plain
        same=_plain(active.city)==_plain(city)
        # A new city invalidates old local catalog scope; it never selects a tenant.
        domain=active.domain if same else 'place'
        await save(db,phone,domain=domain,entity=active.entity,city=city)
        if same:return f'Mantengo la consulta de {active.entity or "locales"} en {city}. No hace falta que repitas la ciudad para esta consulta.'
        return f'La consulta ahora es de {active.entity or "locales"} en {city}. No tengo opciones ni una sede verificadas allí. Si tienes un enlace de esa sede, pásamelo; no usaré el menú ni el delivery de otra ciudad.'
    await save(db,phone,domain='place',city=city)
    from .venezuela import local_options
    local=await local_options(db,city,phone)
    if local:return local
    return f'Para esta consulta usaré {city}. ¿Qué local o tipo de comida quieres buscar? Aún necesito una fuente verificada de esa ciudad.'
