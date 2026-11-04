"""Yummy Rides fare-quote pilot, pull model (GitHub Actions runner edition).

Scope (pilot): quote ONLY, allowlisted phones ONLY. sabi-api owns all
authority: the route, the recipient, the send. The external runner is a
blind executor: it pulls a job (claim) and pushes back ONLY a JPEG
(capture); it never supplies recipient, route or phone.

Flow: inbound WhatsApp quote intent -> job row (pending) -> inputless
GitHub Actions dispatch poke -> runner claims the job over HTTPS (bearer)
-> runner drives the phone -> runner POSTs the JPEG -> sabi-api sends it
to the job's own phone via the configured WhatsApp provider.

Declared limit: delivery is AT-LEAST-ONCE. If the process crashes after
the provider send but before persisting state there is no exactly-once.
Decision: an ambiguous send goes to needs_review and is NEVER resent
blindly; resolution is manual. (Contract-tested.)
"""
from __future__ import annotations

import logging
import re
import secrets
from datetime import timedelta

import httpx
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from .config import settings
from .models import RidesQuoteJob, utcnow
from .whatsapp import digits, send_whatsapp_image, send_whatsapp_message

logger = logging.getLogger("sabi.pilot_yummy")

# pending -> claimed -> sending -> done | needs_review | error
ACTIVE_STATUSES = ("pending", "claimed", "sending", "needs_review")

QUOTE_INTENT = re.compile(
    r"(cu[aá]nto|precio|tarifa|cobra|sale).{0,40}(viaje|carrera|ride|taxi|yummy)", re.IGNORECASE)
RIDE_INTENT = re.compile(
    r"(yummy.{0,40}(taxi|rides?|viaje|carrera|transporte|moto)"
    r"|(taxi|viaje|carrera|transporte|moto).{0,40}yummy"
    r"|(quiero|pido|pedir|solicito|necesito).{0,20}yummy)", re.IGNORECASE)
ROUTE_RE = re.compile(
    r"\b(?:de|desde)\s+(.+?)\s+(?:a|al|hasta|hacia)\s+(.+?)\s*$", re.IGNORECASE)
ROUTE_FOLLOWUP_RE = re.compile(
    r"^(.{1,120}?)\s+(?:a|al|hasta|hacia)\s+(.{1,120}?)\s*$", re.IGNORECASE)
CANCEL_RE = re.compile(
    r"^(no|nada|cancela(r)?|olv[ií]dalo|olvida|d[eé]jalo|mejor no)\b", re.IGNORECASE)
AWAITING_TTL = timedelta(minutes=30)   # route clarification window per phone

JPEG_MAGIC = b"\xff\xd8\xff"
DISPATCH_API = "https://api.github.com/repos/{repo}/actions/workflows/{workflow}/dispatches"


def pilot_allowed(phone: str) -> bool:
    """Digit-normalized on both sides: providers deliver phone in different
    shapes (Zernio digits-only, Meta with country code, etc.)."""
    allowed = {digits(p) for p in settings.rides_pilot_allowed_phones.split(",") if p.strip()}
    return bool(allowed) and digits(phone) in allowed


def verify_runner_token(token: str) -> bool:
    expected = settings.rides_pilot_runner_token
    return bool(expected) and secrets.compare_digest(token, expected)


def verify_admin_token(token: str) -> bool:
    expected = settings.rides_pilot_admin_token
    return bool(expected) and secrets.compare_digest(token, expected)


async def redrive_latest_error_job(db: AsyncSession) -> RidesQuoteJob | None:
    """Manual re-drive (validation/ops): reset the LATEST terminal 'error' job
    to pending and poke dispatch. Terminal done/captured_nosend jobs are
    untouched, and needs_review is NEVER re-driven here: an ambiguous send
    stays under human review."""
    now = utcnow()
    res = await db.execute(
        select(RidesQuoteJob).where(
            (RidesQuoteJob.status == "error") |
            ((RidesQuoteJob.status == "claimed") &
             (RidesQuoteJob.updated_at < now - CLAIMED_TTL)))
        .order_by(RidesQuoteJob.id.desc()).limit(1))
    job = res.scalar_one_or_none()
    if job is None:
        return None
    job.status = "pending"
    job.error = ""
    job.dispatch_poked = False
    job.updated_at = utcnow()
    await db.commit()
    await dispatch_poke(db, job)
    return job


def extract_route(text: str) -> tuple[str, str]:
    """'cuanto cuesta el viaje de X a Y?' -> ('X', 'Y'). Empty when unclear:
    the pilot only runs on an explicit origin AND destination in the message."""
    m = ROUTE_RE.search(text.strip().rstrip("?!."))
    if not m:
        return "", ""
    origin, destination = m.group(1).strip(), m.group(2).strip()
    if not origin or not destination or len(origin) > 200 or len(destination) > 200:
        return "", ""
    return origin, destination


async def daily_job_count(db: AsyncSession, hours: int = 24) -> int:
    since = utcnow() - timedelta(hours=hours)
    res = await db.execute(
        select(func.count()).select_from(RidesQuoteJob)
        .where(RidesQuoteJob.created_at >= since,
               ~RidesQuoteJob.status.in_(("awaiting_route", "expired"))))
    return int(res.scalar() or 0)


async def cap_reached(db: AsyncSession) -> bool:
    return await daily_job_count(db) >= settings.rides_pilot_daily_max


async def active_job_for_phone(db: AsyncSession, phone: str) -> bool:
    """Serialization: at most one active quote job per phone."""
    res = await db.execute(
        select(RidesQuoteJob.id).where(
            RidesQuoteJob.phone == phone,
            RidesQuoteJob.status.in_(ACTIVE_STATUSES)).limit(1))
    return res.first() is not None


async def dispatch_poke(db: AsyncSession, job: RidesQuoteJob) -> bool:
    """Fire the inputless workflow_dispatch. The public run page shows only
    a timestamp: the route travels later over the private claim channel."""
    if job.dispatch_poked:
        return True
    if not settings.gh_dispatch_token:
        logger.error("rides pilot: GH dispatch token not configured; job %s stays pending", job.id)
        return False
    url = DISPATCH_API.format(repo=settings.gh_dispatch_repo,
                              workflow=settings.gh_dispatch_workflow)
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(url, headers={
                "Authorization": f"Bearer {settings.gh_dispatch_token}",
                "Accept": "application/vnd.github+json",
            }, json={"ref": settings.gh_dispatch_ref})
    except httpx.HTTPError as exc:
        logger.error("rides pilot: dispatch poke failed: %s", exc)
        return False
    if resp.status_code >= 400:
        logger.error("rides pilot: dispatch poke refused %s", resp.status_code)
        return False
    job.dispatch_poked = True
    await db.commit()
    return True


REPOKE_AFTER = timedelta(minutes=10)   # pending but dispatch poked long ago -> poke again
CLAIMED_TTL = timedelta(minutes=15)    # runner crashed mid-quote -> one bounded auto-retry
ERROR_RETRY_WINDOW = timedelta(minutes=60)  # fresh "runner timeout" errors get the same single retry
RETRY_MARK = "auto-retry#1"            # stored in job.error: the job already used its one retry

async def recover_stale_jobs(db: AsyncSession) -> None:
    """Best-effort recovery driven by inbound traffic. Duplicate-safe: an
    extra poke only spawns an extra runner run and claim is atomic, so the
    loser is a clean no-op. Ambiguous sends (needs_review) are NEVER
    re-driven automatically: manual review only."""
    now = utcnow()
    res = await db.execute(
        select(RidesQuoteJob).where(RidesQuoteJob.status == "pending"))
    for job in res.scalars():
        age = now - job.updated_at
        if not job.dispatch_poked or age > REPOKE_AFTER:
            job.updated_at = now
            await dispatch_poke(db, job)
    # Runner died mid-quote: re-drive the SAME job once (same row, same
    # route, same recipient; capture stays idempotent, needs_review is never
    # re-driven). Only a second failure notifies the user.
    def retryable(job) -> bool:
        if job.error.startswith(RETRY_MARK):
            return False
        if job.status == "claimed":
            return now - job.updated_at > CLAIMED_TTL
        return (job.status == "error" and job.error == "runner timeout"
                and now - job.updated_at <= ERROR_RETRY_WINDOW)
    res = await db.execute(
        select(RidesQuoteJob).where(
            (RidesQuoteJob.status == "claimed") |
            ((RidesQuoteJob.status == "error") &
             (RidesQuoteJob.error == "runner timeout"))))
    for job in res.scalars():
        if retryable(job):
            job.status = "pending"
            job.dispatch_poked = False
            job.error = RETRY_MARK
            job.updated_at = now
            await db.commit()
            await dispatch_poke(db, job)
        elif job.status == "claimed" and now - job.updated_at > CLAIMED_TTL:
            job.status = "error"
            job.error = "runner timeout after auto-retry"
            await db.commit()
            if not settings.rides_pilot_no_send:
                await send_whatsapp_message(
                    job.phone,
                    "No pude completar la cotización esta vez; si quieres, "
                    "pídemela de nuevo en unos minutos.")

async def _latest_awaiting(db: AsyncSession, phone: str) -> RidesQuoteJob | None:
    res = await db.execute(
        select(RidesQuoteJob).where(
            RidesQuoteJob.phone == phone,
            RidesQuoteJob.status == "awaiting_route")
        .order_by(RidesQuoteJob.updated_at.desc()).limit(1))
    return res.scalars().first()


async def create_quote_job(db: AsyncSession, phone: str, body: str) -> str | None:
    """Webhook branch. Returns the user-facing reply text, or None when the
    message is not a pilot quote request. Never orders a ride: quote only.

    Two-step UX: a ride-intent message without a route gets a clarification
    ("awaiting_route" row, not claimable, outside the active-job index and
    the daily cap); the next route-looking message completes the job. Any
    unrelated message dissolves the awaiting state so normal Sabi flow is
    never hijacked."""
    try:
        await recover_stale_jobs(db)
    except Exception:
        logger.exception("rides pilot recovery sweep failed")
    if not pilot_allowed(phone):
        return None
    if settings.rides_pilot_no_send:
        return None  # validation mode: no new jobs, no user-facing pilot replies
    awaiting = await _latest_awaiting(db, phone)
    if awaiting is not None:
        if utcnow() - awaiting.updated_at > AWAITING_TTL:
            awaiting.status = "expired"
            await db.commit()
        else:
            origin, destination = extract_route(body)
            if not (origin and destination):
                m = ROUTE_FOLLOWUP_RE.search(body.strip().rstrip("?!."))
                if m and "yummy" not in m.group(1).lower():
                    origin, destination = m.group(1).strip(), m.group(2).strip()
            if origin and destination:
                if await cap_reached(db):
                    awaiting.status = "expired"
                    await db.commit()
                    return "Llegu\u00e9 al l\u00edmite de cotizaciones de hoy; ma\u00f1ana puedo seguir."
                awaiting.origin, awaiting.destination = origin, destination
                awaiting.status = "pending"
                awaiting.updated_at = utcnow()
                await db.commit()
                await dispatch_poke(db, awaiting)
                return ("Consultando la tarifa en Yummy Rides, te mando la captura aqu\u00ed "
                        "en unos minutos. Solo es consulta: no se pide ning\u00fan viaje.")
            if CANCEL_RE.search(body.strip()):
                awaiting.status = "expired"
                await db.commit()
                return "Listo, no cotizo nada. Aqu\u00ed sigo por si necesitas otra cosa."
            if RIDE_INTENT.search(body) or QUOTE_INTENT.search(body):
                return ("Dime la ruta as\u00ed: 'de [origen] a [destino]', por ejemplo "
                        "'de MM Plaza a Puertos de Sucre'.")
            # Unrelated message: dissolve the awaiting state, let normal Sabi flow answer.
            awaiting.status = "expired"
            await db.commit()
    if not (QUOTE_INTENT.search(body) or RIDE_INTENT.search(body)):
        return None
    origin, destination = extract_route(body)
    if not (origin and destination):
        job = RidesQuoteJob(phone=phone, origin="", destination="",
                            status="awaiting_route")
        db.add(job)
        await db.commit()
        return ("Con gusto te cotizo el viaje en Yummy Rides. \u00bfDe d\u00f3nde a d\u00f3nde? "
                "Escr\u00edbeme origen y destino, por ejemplo: 'de MM Plaza a Puertos de Sucre'. "
                "Solo es consulta: no se pide ning\u00fan viaje.")
    if await active_job_for_phone(db, phone):
        return ("Ya tengo una cotización en curso para ti; "
                "te mando la captura en cuanto termine.")
    if await cap_reached(db):
        return "Llegué al límite de cotizaciones de hoy; mañana puedo seguir."
    job = RidesQuoteJob(phone=phone, origin=origin, destination=destination)
    db.add(job)
    try:
        await db.commit()
    except Exception:  # unique active-job index lost the race
        await db.rollback()
        return ("Ya tengo una cotización en curso para ti; "
                "te mando la captura en cuanto termine.")
    await dispatch_poke(db, job)
    return ("Consultando la tarifa en Yummy Rides, te mando la captura aquí "
            "en unos minutos. Solo es consulta: no se pide ningún viaje.")


async def claim_next_job(db: AsyncSession) -> RidesQuoteJob | None:
    """Atomic claim: exactly one runner wins each pending job (conditional
    update; the loser's rowcount is 0)."""
    res = await db.execute(
        select(RidesQuoteJob.id).where(RidesQuoteJob.status == "pending")
        .order_by(RidesQuoteJob.id).limit(1))
    row = res.first()
    if row is None:
        return None
    job_id = row[0]
    res = await db.execute(
        update(RidesQuoteJob)
        .where(RidesQuoteJob.id == job_id, RidesQuoteJob.status == "pending")
        .values(status="claimed", updated_at=utcnow()))
    await db.commit()
    if res.rowcount != 1:
        return None
    return await db.get(RidesQuoteJob, job_id)


def valid_jpeg(body: bytes) -> bool:
    """Content check, not Content-Type: real JPEG magic bytes + size cap."""
    return bool(body) and len(body) <= settings.rides_pilot_max_jpeg_bytes \
        and body.startswith(JPEG_MAGIC)


async def capture_job(db: AsyncSession, job_id: int, idem: str, body: bytes) -> tuple[int, dict]:
    """Ingest the runner's screenshot and deliver it to the job's OWN phone.

    Runner supplies ONLY the image + idempotency key. Recipient and route
    come from the job record, never from the request."""
    job = await db.get(RidesQuoteJob, job_id)
    if job is None:
        return 404, {"error": "unknown_job"}
    if not idem:
        return 400, {"error": "missing_idempotency_key"}
    if job.status == "done" and job.idem_key == idem:
        return 200, {"deduped": True}                    # safe replay
    if job.status in ("sending", "needs_review"):
        return 202, {"status": job.status}               # NEVER blind resend
    if job.status != "claimed":
        return 409, {"error": "bad_state"}
    if not valid_jpeg(body):
        return 400, {"error": "invalid_jpeg"}
    job.idem_key = idem
    if settings.rides_pilot_no_send:
        # Validation mode: prove the whole journey (claim -> Yummy -> JPEG ->
        # ingest) with ZERO WhatsApp sends. Status frees the phone; the row
        # keeps the route private and is never re-driven.
        job.status = "captured_nosend"
        await db.commit()
        logger.info("rides pilot: job %s captured in no-send mode (%d bytes)", job.id, len(body))
        return 200, {"deduped": False, "no_send": True}
    job.status = "sending"
    await db.commit()
    caption = f"Tarifa Yummy Rides: {job.origin} → {job.destination}"
    result = await send_whatsapp_image(job.phone, body, caption, idempotency_key=idem)
    if result.get("error"):
        # Ambiguous: the send may have left. No automatic retry.
        job.status = "needs_review"
        job.error = str(result.get("error"))[:300]
        await db.commit()
        logger.error("rides pilot: job %s needs_review after ambiguous send", job.id)
        return 202, {"status": "needs_review"}
    job.status = "done"
    await db.commit()
    return 200, {"deduped": False}
