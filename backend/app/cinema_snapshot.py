"""Durable dated cinema snapshots. Prepared only: no production route/cron enabled."""
import json
from datetime import datetime,timedelta
from zoneinfo import ZoneInfo
from sqlalchemy import String,Text,DateTime,UniqueConstraint,select
from sqlalchemy.orm import Mapped,mapped_column
from .models import Base

TZ=ZoneInfo('America/Caracas')
class CinemaSnapshot(Base):
    __tablename__='cinema_snapshots'
    __table_args__=(UniqueConstraint('provider','venue_key','show_date',name='uq_cinema_snapshot_venue_date'),)
    id:Mapped[int]=mapped_column(primary_key=True)
    provider:Mapped[str]=mapped_column(String(30))
    venue_key:Mapped[str]=mapped_column(String(100))
    venue_name:Mapped[str]=mapped_column(String(150))
    city:Mapped[str]=mapped_column(String(100))
    show_date:Mapped[str]=mapped_column(String(10))
    fetched_at:Mapped[datetime]=mapped_column(DateTime(timezone=True))
    expires_at:Mapped[datetime]=mapped_column(DateTime(timezone=True))
    payload:Mapped[str]=mapped_column(Text)
    markdown:Mapped[str]=mapped_column(Text)


def aware(d):return d.replace(tzinfo=TZ) if d.tzinfo is None else d

def line(s):return ' '.join(str(s).replace('|','/').split())

def markdown_for(payload,*,provider,venue_key,venue_name,city,show_date,fetched_at,expires_at):
    rows=[f'# Cartelera: {line(venue_name)}', '',f'- Proveedor: {line(provider)}',f'- Sede: {line(venue_key)}',
          f'- Ciudad: {line(city)}',f'- Fecha de funciones: {show_date}',f'- Consultada: {fetched_at.isoformat()}',
          f'- Caduca: {expires_at.isoformat()}', '- Zona horaria: America/Caracas',
          '- Vigencia: una lectura publicada no garantiza venta ni asientos. No usar después de caducar.', '', '## Fuentes']
    rows += [f'- {x["url"]} (lectura: {x.get("fetched_at",fetched_at.isoformat())}; caché proveedor: {bool(x.get("cached"))})' for x in payload.get('sources',[])]
    rows += ['', '## Funciones', '', '| Película | Hora local | Venta |','| --- | --- | --- |']
    for x in sorted(payload.get('items',[]),key=lambda x:x.get('time','')):
        channel='Sólo taquilla' if x.get('sales_channel')=='box_office_only' else 'Modalidad no verificada'
        rows.append(f'| {line(x.get("name",""))} | {line(x.get("time",""))} | {channel} |')
    if not payload.get('items'):rows+=['','La fuente devolvió una lista completa sin funciones para esta fecha.']
    if payload.get('warnings'):rows+=['','## Límites']+[f'- {line(x)}' for x in payload['warnings']]
    return '\n'.join(rows)+'\n'

async def store_snapshot(db,payload,*,provider,venue_key,venue_name,city,show_date,now=None):
    """Only complete venue+day reads may replace the last good snapshot."""
    now=now or datetime.now(TZ)
    if payload.get('status')!='available' or payload.get('partial') or payload.get('next_offset') is not None:
        raise ValueError('incomplete source must not replace snapshot')
    if not payload.get('sources'):raise ValueError('source required')
    if payload.get('total')!=len(payload.get('items',[])):raise ValueError('pagination incomplete')
    day=datetime.fromisoformat(show_date).date()
    if day<now.astimezone(TZ).date():raise ValueError('past day')
    for x in payload.get('items',[]):
        if x.get('date')!=show_date or x.get('cinema_name')!=venue_name:raise ValueError('venue/date mismatch')
    source_dates=[datetime.fromisoformat(x['fetched_at'].replace('Z','+00:00')) for x in payload['sources'] if x.get('fetched_at')]
    if not source_dates:raise ValueError('source time required')
    oldest=min(source_dates)
    end=datetime.combine(day+timedelta(days=1),datetime.min.time(),tzinfo=TZ)
    expires=min(oldest+timedelta(hours=24),end)
    if expires<=now:raise ValueError('source already stale')
    row=(await db.execute(select(CinemaSnapshot).where(CinemaSnapshot.provider==provider,CinemaSnapshot.venue_key==venue_key,CinemaSnapshot.show_date==show_date))).scalar_one_or_none()
    if row is None:row=CinemaSnapshot(provider=provider,venue_key=venue_key,venue_name=venue_name,city=city,show_date=show_date);db.add(row)
    row.fetched_at=now;row.expires_at=expires;row.payload=json.dumps(payload,ensure_ascii=False)
    row.markdown=markdown_for(payload,provider=provider,venue_key=venue_key,venue_name=venue_name,city=city,show_date=show_date,fetched_at=now,expires_at=expires)
    await db.flush();return row

async def read_snapshot(db,*,provider,venue_key,show_date,now=None):
    now=now or datetime.now(TZ)
    row=(await db.execute(select(CinemaSnapshot).where(CinemaSnapshot.provider==provider,CinemaSnapshot.venue_key==venue_key,CinemaSnapshot.show_date==show_date))).scalar_one_or_none()
    if not row or aware(row.expires_at)<=now:return None
    data=json.loads(row.payload)
    data['items']=[x for x in data.get('items',[]) if datetime.fromisoformat(x['starts_at'])>now]
    data['total']=len(data['items']);data['snapshot']={'fetched_at':aware(row.fetched_at).isoformat(),'expires_at':aware(row.expires_at).isoformat()}
    return data

async def snapshot_first(db,*,provider,venue_key,venue_name,city,show_date,loader,now=None):
    """Prepared integration seam: fresh DB first, refresh once on miss; never stale fallback."""
    hit=await read_snapshot(db,provider=provider,venue_key=venue_key,show_date=show_date,now=now)
    if hit is not None:return hit
    result=await loader()
    await store_snapshot(db,result,provider=provider,venue_key=venue_key,venue_name=venue_name,city=city,show_date=show_date,now=now)
    await db.commit()
    return await read_snapshot(db,provider=provider,venue_key=venue_key,show_date=show_date,now=now)
