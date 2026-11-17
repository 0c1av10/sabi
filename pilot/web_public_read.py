"""Manual anonymous read/capture. Never sends a WhatsApp message or deploys."""
import asyncio
import json
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'backend'))
from app.public_web_worker import run_public_read
if __name__=='__main__':
    result=asyncio.run(run_public_read(sys.argv[1],sys.argv[2],Path(sys.argv[3])))
    print(json.dumps({k:result[k] for k in ('site','source_url','selected_url','requests','bytes','results')},ensure_ascii=False))
