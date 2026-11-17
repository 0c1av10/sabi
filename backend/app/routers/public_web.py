"""Private pull-worker API, deliberately no auto-dispatch or public evidence URLs."""
import secrets
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession
from ..config import settings
from ..db import get_db
from .. import public_web_jobs
router=APIRouter(prefix='/api/pilot/public-web',tags=['public-web-pilot'])


def authorize(request):
    if not settings.public_web_pilot_enabled or not settings.public_web_worker_token:
        raise HTTPException(404)
    actual=request.headers.get('authorization','')
    if not secrets.compare_digest(actual,'Bearer '+settings.public_web_worker_token):raise HTTPException(401)


@router.post('/claim')
async def claim(request:Request,db:AsyncSession=Depends(get_db)):
    authorize(request)
    return {'job':await public_web_jobs.claim(db)}


@router.post('/jobs/{job_id}/capture')
async def capture(job_id:int,request:Request,db:AsyncSession=Depends(get_db)):
    authorize(request)
    data=bytearray()
    async for chunk in request.stream():
        data.extend(chunk)
        if len(data)>1_000_000:raise HTTPException(413)
    try:return await public_web_jobs.complete(db,job_id,request.headers.get('x-job-claim',''),bytes(data))
    except ValueError as exc:raise HTTPException(409,detail=str(exc)) from exc
