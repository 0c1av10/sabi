"""One-shot pull worker. Requires an approved host plus separately configured secret.
No scheduler/dispatch, no phone harness, no merchant account, no AI API.
Never logs token, phone, query, page text or captured images. Re-run manually only
for a NEW pending job; a claimed/ambiguous job is not automatically retried.
"""
import asyncio
import os
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
from urllib.parse import urlsplit
import httpx
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'backend'))
from app.public_web_worker import run_public_read

async def main():
    base=os.environ.get('SABI_PUBLIC_WEB_API','').rstrip('/')
    token=os.environ.get('SABI_PUBLIC_WEB_WORKER_TOKEN','')
    p=urlsplit(base)
    if p.scheme!='https' or p.hostname!=os.environ.get('SABI_PUBLIC_WEB_API_HOST','') or p.path or p.query or p.fragment or p.username or p.password or p.port not in (443,None) or not token:
        raise SystemExit('An approved Sabi HTTPS endpoint and worker credential are required.')
    async with httpx.AsyncClient(headers={'Authorization':'Bearer '+token},timeout=120,follow_redirects=False,trust_env=False) as client:
        claimed=await client.post(base+'/api/pilot/public-web/claim');claimed.raise_for_status()
        job=claimed.json().get('job')
        if not job: print('No pending job.');return
        with TemporaryDirectory(prefix='sabi-public-') as tmp:
            report=await run_public_read(job['site'],job['query'],Path(tmp))
            # A single decision capture. Worker cannot choose recipient/caption.
            chosen=report['captures'][-1]
            image=(Path(tmp)/chosen['file']).read_bytes()
            result=await client.post(base+f'/api/pilot/public-web/jobs/{int(job["id"])}/capture',
                content=image,headers={'Content-Type':'image/jpeg','X-Job-Claim':job['claim']})
            result.raise_for_status()
            print('Public read finished:',result.json().get('status','unknown'))

if __name__=='__main__':asyncio.run(main())
