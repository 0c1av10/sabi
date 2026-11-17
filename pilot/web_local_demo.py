"""Real local Chromium exercise. Blocks every request outside one loopback server.

No merchant integration, no cloud/browser billing, no AI calls, no real WhatsApp.
Run with installed playwright and an existing local Chromium.
"""
import asyncio
from dataclasses import asdict
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import sys
from threading import Thread
from urllib.parse import urlsplit

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'backend'))
from app.web_tasks import WebTask, validate_action
from app.web_captures import capture_fixture_step


async def exercise(browser, base: str, out: Path):
    context=await browser.new_context(service_workers='block', viewport={'width':390,'height':1100}, device_scale_factor=1)
    blocked=[]
    async def guard(route):
        p=urlsplit(route.request.url)
        if (route.request.method != 'GET' or p.scheme!='http' or
                p.netloc!=urlsplit(base).netloc):
            blocked.append(route.request.url)
            await route.abort()
        else:
            await route.continue_()
    await context.route('**/*',guard)
    await context.route_web_socket('**/*',lambda ws:ws.close())
    page=await context.new_page()
    await page.goto(base,wait_until='load')
    images=[await capture_fixture_step(page,'page_loaded',environment='fixture')]
    task=WebTask('mitickera','Entradas, después dos por favor')
    task.update_facts(query='Concierto de prueba')
    task.update_facts(quantity='2')
    validate_action('fill','query')
    await page.locator('#query').fill(task.facts['query'])
    validate_action('select','quantity')
    await page.locator('#quantity').select_option(task.facts['quantity'])
    images.append(await capture_fixture_step(page,'selection_updated',environment='fixture'))
    text=await page.locator('section').inner_text()
    assert 'US$20' in text and 'Sin enviar ni pagar' in text
    task.record(base,text,environment='fixture')
    task.ready_for_review()
    images.append(await capture_fixture_step(page,'decision_needed',environment='fixture'))
    # Deliberately try an outbound request: the network guard must block it.
    await page.evaluate("fetch('https://example.com/outbound-must-be-blocked').catch(()=>null)")
    assert blocked==['https://example.com/outbound-must-be-blocked']
    await page.screenshot(path=str(out/'web-local-demo.png'),full_page=True)
    # Actual JPEGs pass into Sabi's existing image adapter, but ALL HTTP uses
    # MockTransport. No provider/account is called. Acceptance is NOT delivery.
    import httpx
    from app import whatsapp as wa
    from app.config import settings
    from unittest.mock import patch
    calls=[]
    def fake_provider(req):
        assert req.method=='POST' and b'image/jpeg' in req.content
        assert b'PRUEBA LOCAL' in req.content
        assert b'attachment' in req.content and b'\xff\xd8\xff' in req.content
        calls.append(req)
        return httpx.Response(200,json={'success':True,'data':{'id':f'fixture-{len(calls)}'}})
    client=httpx.AsyncClient
    manifest=[]
    last_jpeg=None
    with patch.object(settings,'whatsapp_provider','zernio'), patch.object(settings,'whatsapp_mock_mode',False), patch.object(settings,'zernio_api_key','fixture-not-a-key'), patch.object(settings,'zernio_account_id','fixture-account'), patch.dict(wa.zernio_conversations,{'59900000000':'fixture-conversation'}), patch.object(wa.httpx,'AsyncClient',lambda **kw:client(transport=httpx.MockTransport(fake_provider),**kw)):
        for i,image in enumerate(images,1):
            path=out/f'step-{i}-{image.stage}.jpg'
            path.write_bytes(image.jpeg)
            duplicate=image.jpeg==last_jpeg
            if not duplicate:
                result=await wa.send_whatsapp_image('59900000000',image.jpeg,image.caption,idempotency_key=image.idempotency_key)
                assert result.get('success') is True
            last_jpeg=image.jpeg
            manifest.append({'stage':image.stage,'caption':image.caption,'file':path.name,'environment':'fixture','transport':'httpx.MockTransport','duplicate_image_skipped':duplicate,'visible_delivery_verified':False})
    assert len(calls)==2
    (out/'step-images.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2))
    result={**asdict(task),'summary':task.summary(),'blocked_outbound':len(blocked)}
    (out/'web-local-demo.json').write_text(json.dumps(result,ensure_ascii=False,indent=2))
    await context.close()
    return result


async def main(out: Path):
    from playwright.async_api import async_playwright
    import shutil
    class QuietHandler(SimpleHTTPRequestHandler):
        def log_message(self,*args): pass
    server=ThreadingHTTPServer(('127.0.0.1',0),partial(QuietHandler,directory=str(ROOT/'pilot/web_fixtures')))
    thread=Thread(target=server.serve_forever,daemon=True);thread.start()
    out.mkdir(parents=True,exist_ok=True)
    try:
        async with async_playwright() as p:
            chrome=shutil.which('google-chrome-stable') or shutil.which('chromium')
            browser=await p.chromium.launch(executable_path=chrome,headless=True,args=['--no-sandbox'])
            try:
                result=await exercise(browser,f'http://127.0.0.1:{server.server_port}/',out)
                print(json.dumps({'state':result['state'],'environment':'fixture','outbound_blocked':result['blocked_outbound'],'step_images':3,'image_transport':'offline_mock','image_uploads':2},ensure_ascii=False))
            finally: await browser.close()
    finally:
        server.shutdown();server.server_close();thread.join()

if __name__=='__main__':
    asyncio.run(main(Path(sys.argv[1]) if len(sys.argv)>1 else Path('/tmp/sabi-web-demo')))
