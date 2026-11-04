"""Yummy Rides quote pilot: runner-facing endpoints (pull model).

Not user-facing. The user leg is the WhatsApp webhook (service.py). These
two endpoints serve the GitHub Actions runner only, authenticated with a
shared bearer token (constant-time compared). The runner pulls work and
pushes back ONLY a JPEG; recipient/route authority stays in the job row.
"""
import json

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlalchemy.ext.asyncio import AsyncSession

from .. import pilot_yummy
from ..config import settings
from ..db import get_db
from ..models import RidesDiagReport, RidesDiagShot, RidesQuoteJob

router = APIRouter(prefix="/api/pilot/yummy", tags=["pilot-yummy"])


async def _auth(request: Request) -> None:
    token = request.headers.get("authorization", "")
    scheme, _, value = token.partition(" ")
    if scheme.lower() != "bearer" or not pilot_yummy.verify_runner_token(value):
        raise HTTPException(status_code=401, detail="bad token")


async def _auth_admin(request: Request) -> None:
    token = request.headers.get("authorization", "")
    scheme, _, value = token.partition(" ")
    if scheme.lower() != "bearer" or not pilot_yummy.verify_admin_token(value):
        raise HTTPException(status_code=401, detail="bad token")


@router.post("/diag/{job_id}/report", status_code=200)
async def diag_report_upload(job_id: int, request: Request, db: AsyncSession = Depends(get_db)):
    """Private text diagnostics (GPS, permissions, network). Runner OR admin
    token: local diagnostic sessions hold the admin token only."""
    try:
        await _auth(request)
    except HTTPException:
        await _auth_admin(request)
    body = (await request.body())[:60000]
    db.add(RidesDiagReport(job_id=job_id, report=body.decode("utf-8", "replace")))
    await db.commit()
    return {"stored": True}


@router.get("/diag/{job_id}/report")
async def diag_report_latest(job_id: int, request: Request, db: AsyncSession = Depends(get_db)):
    await _auth_admin(request)
    from sqlalchemy import select
    res = await db.execute(
        select(RidesDiagReport).where(RidesDiagReport.job_id == job_id)
        .order_by(RidesDiagReport.id.desc()).limit(1))
    rep = res.scalar_one_or_none()
    if rep is None:
        return Response(status_code=204)
    return {"report": rep.report, "created_at": rep.created_at.isoformat()}


@router.get("/jobs/{job_id}", status_code=200)
async def job_detail(job_id: int, request: Request, db: AsyncSession = Depends(get_db)):
    """Admin-only private read of a pilot job (route is private data; never
    appears in public runner logs)."""
    await _auth_admin(request)
    job = await db.get(RidesQuoteJob, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="job_not_found")
    return {"job_id": str(job.id), "status": job.status, "origin": job.origin,
            "destination": job.destination, "error": job.error,
            "created_at": job.created_at.isoformat(),
            "updated_at": job.updated_at.isoformat()}


@router.post("/jobs/redrive", status_code=200)
async def redrive(request: Request, db: AsyncSession = Depends(get_db)):
    """Ops-only manual re-drive of the latest errored job (validation flow).
    Separate admin token, NOT the runner token: capture/claim stay runner-only."""
    await _auth_admin(request)
    job = await pilot_yummy.redrive_latest_error_job(db)
    if job is None:
        return Response(status_code=204)
    return {"job_id": str(job.id), "status": job.status}


@router.post("/diag/{job_id}", status_code=200)
async def diag_upload(job_id: int, request: Request, db: AsyncSession = Depends(get_db)):
    """Runner uploads a private failure screenshot. Does NOT touch the job
    row: diagnostics never advance or close a job."""
    await _auth(request)
    body = await request.body()
    if len(body) > settings.rides_pilot_max_jpeg_bytes or not pilot_yummy.valid_jpeg(body):
        raise HTTPException(status_code=400, detail="invalid_jpeg")
    reason = request.headers.get("x-diag-reason", "")[:160]
    db.add(RidesDiagShot(job_id=job_id, reason=reason, image=body))
    await db.commit()
    return {"stored": True}


@router.get("/diag/{job_id}")
async def diag_latest(job_id: int, request: Request, db: AsyncSession = Depends(get_db)):
    """Admin-only retrieval of the latest diagnostic shot for a job."""
    await _auth_admin(request)
    from sqlalchemy import select
    res = await db.execute(
        select(RidesDiagShot).where(RidesDiagShot.job_id == job_id)
        .order_by(RidesDiagShot.id.desc()).limit(1))
    shot = res.scalar_one_or_none()
    if shot is None:
        return Response(status_code=204)
    return Response(content=bytes(shot.image), media_type="image/jpeg",
                    headers={"X-Diag-Reason": shot.reason,
                             "X-Diag-At": shot.created_at.isoformat()})


@router.post("/jobs/claim", status_code=200)
async def claim(request: Request, db: AsyncSession = Depends(get_db)):
    await _auth(request)
    try:
        # The runner's arrival doubles as the recovery heartbeat: a dead
        # runner leaves no inbound traffic to drive the sweep.
        await pilot_yummy.recover_stale_jobs(db)
    except Exception:
        pass
    job = await pilot_yummy.claim_next_job(db)
    if job is None:
        return Response(status_code=204)
    return {"job_id": str(job.id), "origin": job.origin, "dest": job.destination}


@router.post("/jobs/{job_id}/capture")
async def capture(job_id: int, request: Request, db: AsyncSession = Depends(get_db)):
    await _auth(request)
    body = await request.body()
    idem = request.headers.get("idempotency-key", "")
    code, payload = await pilot_yummy.capture_job(db, job_id, idem, body)
    return Response(content=json.dumps(payload), status_code=code,
                    media_type="application/json")
