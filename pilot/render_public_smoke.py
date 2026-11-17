"""ONE public-read smoke, no API credential or WhatsApp. Operator stops service.

No jobs are polled, no repetition, no self-restart after exception. Holding an
idle worker still bills: operator must suspend/delete it immediately after review.
"""
import asyncio
import json
from pathlib import Path
import resource
import sys
from tempfile import TemporaryDirectory
import time
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'backend'))
from app.public_web_worker import run_public_read

async def main():
    try:
        with TemporaryDirectory(prefix='sabi-smoke-') as tmp:
            report=await run_public_read('yummy','audifonos',Path(tmp))
            assert report['environment']=='live_public_anonymous' and report['results']
            assert report['selected_url'].startswith('https://yummy-marketplace.com/producto/')
            assert len(report['captures'])==3
            print(json.dumps({'event':'PUBLIC_WEB_SMOKE_OK','environment':report['environment'],
                'source_url':report['source_url'],'selected_url':report['selected_url'],
                'results':len(report['results']),'captures':len(report['captures']),
                'sha256':[s['sha256'] for s in report['captures']],
                'maxrss_kib':resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss,
                'whatsapp_sent':False,'merchant_login':False,'purchase':False}),flush=True)
    except Exception as exc:
        print(json.dumps({'event':'PUBLIC_WEB_SMOKE_FAILED','error_class':type(exc).__name__}),flush=True)
    print('ONE_SHOT_FINISHED_STOP_SERVICE_NOW. No more network work will run.',flush=True)
    while True:await asyncio.sleep(3600)

if __name__=='__main__':asyncio.run(main())
