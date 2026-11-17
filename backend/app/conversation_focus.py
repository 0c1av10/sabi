"""Per-user, 30-minute explicit task state. No inferred tastes or external search."""
import re
from datetime import datetime,timedelta
from sqlalchemy import String,DateTime,select,delete
from sqlalchemy.orm import Mapped,mapped_column
from .models import Base,utcnow
from .whatsapp import digits
from . import concierge

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
    return (await db.execute(select(ConversationFocus).where(ConversationFocus.phone==digits(phone),ConversationFocus.expires_at>now).execution_options(populate_existing=True))).scalar_one_or_none()

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
    text=concierge._plain(body).strip(' ¿?!.')
    match=ENTITY.match(body.strip())
    if match:
        await save(db,phone,domain='place',entity=match[1])
        return f'¿En qué ciudad queda {match[1]}?'
    if not (re.search(r'\b(pizzeria|restaurante|local)\b',text) or text in ('buscala','buscalo','busca')):return None
    focus=await get(db,phone)
    if not focus or focus.domain not in ('place','restaurant'):return None
    if re.search(r'\b(pizzeria|restaurante|local)\b',text):
        # Only explicit city patterns, never GPS or guessed neighboring city.
        citymatch=re.search(r'\ben\s+([a-záéíóúñ ]+?)(?:\s+en la |\s+por |$)',body,re.I)
        city=citymatch[1].strip().title() if citymatch else focus.city
        await save(db,phone,domain='restaurant',entity=focus.entity,city=city)
        return f'Entendido: {focus.entity}'+(f' en {city}.' if city else '. ¿En qué ciudad queda?')
    if text in ('buscala','buscalo','busca'):
        if not focus.city:return f'¿En qué ciudad queda {focus.entity}?'
        return f'Mantengo la consulta de {focus.entity} en {focus.city}. La búsqueda web de locales aún no está conectada; no tengo una fuente nueva para darte datos verificados.'
    return None
