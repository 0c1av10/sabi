"""Opt-in queue for public reads. No automatic dispatch, accounts or purchases.

The server owns phone/site/query/source. Worker never chooses the recipient.
Delivery is independent and OFF by default. Ambiguous sends are never retried.
No image persistence: max 1MB in memory, discarded after the one-shot result.
"""
from datetime import timedelta
import hashlib
import re
import secrets
from urllib.parse import urlencode
from sqlalchemy import select, update, func
from sqlalchemy.exc import IntegrityError
from .config import settings
from .models import PublicWebJob, utcnow
from .whatsapp import digits, send_whatsapp_image

COMMAND=re.compile(r'^(?:/web\s+(yummy|mitickera)\s+(.{1,100})|busca\s+(.{1,100}?)\s+en\s+(yummy(?: marketplace)?|mitickera))$',re.I)


def allowed(phone):
    return settings.public_web_pilot_enabled and digits(phone) in {digits(x) for x in settings.public_web_allowed_phones.split(',') if x.strip()}


def parse_command(body):
    m=COMMAND.fullmatch(body.strip())
    if not m:return None
    site=(m[1] or m[4]).lower().replace(' marketplace','')
    query=(m[2] or m[3]).strip()
    if any(ord(c)<32 for c in query) or 'http' in query.lower() or '@' in query or re.search(r'\d{7,}',query):return None
    return site,query


def source_url(job):
    return ('https://yummy-marketplace.com/productos?'+urlencode({'q':job.query})
            if job.site=='yummy' else 'https://www.mitickera.com/eventos/')


async def expire_jobs(db):
    await db.execute(update(PublicWebJob).where(PublicWebJob.expires_at<=utcnow(),PublicWebJob.status.in_(('pending','claimed'))).values(status='expired',claim_hash=''))
    await db.commit()


async def enqueue(db,phone,body,external_id):
    parsed=parse_command(body)
    if not allowed(phone) or not parsed:return None
    await expire_jobs(db)
    if not settings.public_web_worker_token:
        return 'La lectura de páginas aún no está habilitada. No hice ninguna búsqueda ni compra.'
    if not external_id:
        return 'Esta prueba necesita un mensaje entrante identificado; no inicié la tarea.'
    old=await db.scalar(select(PublicWebJob).where(PublicWebJob.external_id==external_id))
    if old:return 'Esa consulta ya está registrada; no la duplico.'
    active=await db.scalar(select(PublicWebJob.id).where(PublicWebJob.phone==digits(phone),PublicWebJob.status.in_(('pending','claimed','needs_review'))))
    if active:return 'Ya hay una consulta en curso. No he creado otra.'
    n=await db.scalar(select(func.count()).select_from(PublicWebJob).where(PublicWebJob.created_at>=utcnow()-timedelta(days=1)))
    if (n or 0)>=settings.public_web_daily_max:return 'La prueba llegó a su límite diario. No inicié otra consulta.'
    site,query=parsed
    db.add(PublicWebJob(phone=digits(phone),site=site,query=query,external_id=external_id,
        expires_at=utcnow()+timedelta(minutes=15)))
    try:await db.commit()
    except IntegrityError:
        await db.rollback();return 'Esa consulta ya está en curso; no la duplico.'
    return f'Consultaré {query} en {"Yummy Marketplace" if site=="yummy" else "MiTickera"}. Solo lectura pública; no compraré, reservaré ni contactaré a nadie.'


async def claim(db):
    await expire_jobs(db)
    # A single conditional UPDATE makes concurrent claims mutually exclusive.
    candidate=select(PublicWebJob.id).where(PublicWebJob.status=='pending',PublicWebJob.expires_at>utcnow()).order_by(PublicWebJob.id).limit(1).scalar_subquery()
    nonce=secrets.token_urlsafe(32)
    row=(await db.execute(update(PublicWebJob).where(PublicWebJob.id==candidate,PublicWebJob.status=='pending').values(status='claimed',claim_hash=hashlib.sha256(nonce.encode()).hexdigest()).returning(PublicWebJob.id,PublicWebJob.site,PublicWebJob.query))).first()
    await db.commit()
    return {'id':row.id,'site':row.site,'query':row.query,'claim':nonce} if row else None


async def complete(db,job_id,nonce,jpeg):
    job=await db.get(PublicWebJob,job_id)
    if not job or job.status!='claimed' or job.expires_at<=utcnow() or not secrets.compare_digest(job.claim_hash,hashlib.sha256(nonce.encode()).hexdigest()):
        raise ValueError('invalid_or_expired_claim')
    if not jpeg.startswith(b'\xff\xd8\xff') or len(jpeg)>1_000_000:
        raise ValueError('invalid_image')
    job.summary=f'Captura de una consulta pública sobre {job.query}. Fuente: {source_url(job)}. No es confirmación de disponibilidad, carrito, reserva ni compra.'
    job.status='captured_nosend'
    # No image is stored or exposed by an endpoint. No user phone in worker response.
    if settings.public_web_delivery_enabled and allowed(job.phone):
        job.status='needs_review'
        await db.commit()  # Crash or ambiguous send stays here, never requeued.
        result=await send_whatsapp_image(job.phone,jpeg,job.summary,idempotency_key=f'public-web-{job.id}')
        if result.get('success'):
            job.status='done'
    await db.commit()
    return {'status':job.status,'sent':job.status=='done'}
