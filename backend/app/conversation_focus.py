"""Bounded explicit focus, not inferred tastes. Preparation pending production schema review."""
import re
from datetime import datetime,timedelta
from sqlalchemy import String, DateTime
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
    expires_at:Mapped[datetime]=mapped_column(DateTime)

async def get(db,phone):
    row=await db.get(ConversationFocus,digits(phone))
    return row if isinstance(row,ConversationFocus) and row.expires_at>utcnow() else None

async def forget(db,phone):
    row=await db.get(ConversationFocus,digits(phone))
    if row:
        await db.delete(row);await db.commit()

async def set_focus(db,phone,domain,entity='',city=''):
    row=await db.get(ConversationFocus,digits(phone)) or ConversationFocus(phone=digits(phone))
    row.domain,row.entity,row.city=domain,entity[:100],city[:100]
    row.expires_at=utcnow()+timedelta(minutes=30)
    db.add(row);await db.commit();return row

ENTITY=re.compile(r'^(?:sabes? (?:que|qué) es|conoces|busca(?:me)?(?: el| la)?(?: restaurante| pizzeria)?)\s+(.+?)\??$',re.I)
FOOD=re.compile(r'\b(pizzerias?|restaurantes?|restaurantes?|pizza|comida|comer|cenar|delivery|hamburguesas?)\b')
SEARCH=re.compile(r'^(?:buscal[ao]|busca|buscal[ao] por favor)[.!?]*$')

async def route(db,phone,body):
    """Return a bounded reply only for cross-domain inquiry, not regular merchant ordering."""
    text=concierge._plain(body).strip()
    focus=await get(db,phone)
    match=ENTITY.match(body.strip())
    if match:
        entity=match[1].strip()[:100]
        await set_focus(db,phone,'place',entity)
        return f'¿En qué ciudad queda {entity}?'
    if FOOD.search(text) and focus and focus.domain=='place':
        city='Lechería' if re.search(r'\blecheria\b',text) else focus.city
        await set_focus(db,phone,'restaurant',focus.entity,city)
        return f'Entendido: buscas información de {focus.entity}'+(f' en {city}.' if city else '. ¿En qué ciudad queda?')
    if SEARCH.match(text) and focus and focus.domain in ('place','restaurant'):
        if not focus.city:return f'¿En qué ciudad queda {focus.entity}?'
        from .place_directory import lookup
        return lookup(focus.entity,focus.city)
    if FOOD.search(text):
        await set_focus(db,phone,'restaurant',focus.entity if focus and focus.domain=='restaurant' else '',focus.city if focus else '')
    return None
