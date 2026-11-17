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


async def exercise(browser, base: str, out: Path):
    context=await browser.new_context(service_workers='block')
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
    task=WebTask('mitickera','Entradas, después dos por favor')
    task.update_facts(query='Concierto de prueba')
    task.update_facts(quantity='2')
    validate_action('fill','query')
    await page.locator('#query').fill(task.facts['query'])
    validate_action('select','quantity')
    await page.locator('#quantity').select_option(task.facts['quantity'])
    text=await page.locator('section').inner_text()
    assert 'US$20' in text and 'Sin enviar ni pagar' in text
    task.record(base,text,environment='fixture')
    task.ready_for_review()
    # Deliberately try an outbound request: the network guard must block it.
    await page.evaluate("fetch('https://example.com/outbound-must-be-blocked').catch(()=>null)")
    assert blocked==['https://example.com/outbound-must-be-blocked']
    await page.screenshot(path=str(out/'web-local-demo.png'),full_page=True)
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
                print(json.dumps({'state':result['state'],'environment':'fixture','outbound_blocked':result['blocked_outbound']},ensure_ascii=False))
            finally: await browser.close()
    finally:
        server.shutdown();server.server_close();thread.join()

if __name__=='__main__':
    asyncio.run(main(Path(sys.argv[1]) if len(sys.argv)>1 else Path('/tmp/sabi-web-demo')))
