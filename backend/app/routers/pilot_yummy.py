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
from ..db import get_db

router = APIRouter(prefix="/api/pilot/yummy", tags=["pilot-yummy"])


async def _auth(request: Request) -> None:
    token = request.headers.get("authorization", "")
    scheme, _, value = token.partition(" ")
    if scheme.lower() != "bearer" or not pilot_yummy.verify_runner_token(value):
        raise HTTPException(status_code=401, detail="bad token")


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
