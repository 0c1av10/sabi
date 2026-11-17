"""Reproducible anonymous public read/capture; no WhatsApp, account or checkout.

Usage: python pilot/web_public_read.py yummy audifonos OUTPUT
       python pilot/web_public_read.py mitickera natalia OUTPUT
Not a production worker. Browser network is intercepted and fulfilled only by
PublicReader; no cookies or request headers are forwarded. One run per site,
not a monitor. Rendering is partial when third-party resources are blocked.
"""
import asyncio
from dataclasses import asdict
import hashlib
import json
from pathlib import Path
import shutil
import sys
from .public_web import PublicReader, PublicWebError, VisibleHTML
from urllib.parse import urlencode


async def run_public_read(site,query,out):
    from playwright.async_api import async_playwright
    reader=PublicReader(site,query)
    urls={'yummy':'https://yummy-marketplace.com/productos?'+urlencode({'q':query}),
          'mitickera':'https://www.mitickera.com/eventos/'}
    if site not in urls:raise ValueError('site_not_enabled_after_access_denial')
    url=urls[site];out.mkdir(parents=True,exist_ok=True)
    blocked=[];results=[];lock=asyncio.Lock()
    async def route_request(route):
        req=route.request
        try:
            # Serialize to enforce shared budgets deterministically.
            async with lock:
                response=await asyncio.to_thread(reader.fetch,req.url,req.method,req.post_data)
            if response.status in (401,403,429):
                blocked.append({'url':req.url,'reason':f'http_{response.status}'})
            # Never copy response cookies or allow response redirects in Chromium.
            cors={'content-type':response.content_type,'access-control-allow-origin':'https://yummy-marketplace.com'}
            await route.fulfill(status=response.status,headers=cors,body=response.body)
            if req.method=='POST' and response.status==200:
                data=json.loads(response.body)
                data=data.get('body',data.get('data',data))
                # Public product evidence, not personal seller info or session IDs.
                results.extend({k:h.get(k) for k in ('objectID','title','price','currency','inStock')} for h in data.get('hits',[])[:12])
        except Exception as exc:
            blocked.append({'url':req.url.split('?')[0],'reason':str(exc) if isinstance(exc,PublicWebError) else type(exc).__name__})
            await route.abort()
    async with async_playwright() as p:
        chrome=shutil.which('google-chrome-stable') or shutil.which('chromium')
        browser=await p.chromium.launch(executable_path=chrome,headless=True,args=['--no-sandbox','--disable-background-networking','--force-webrtc-ip-handling-policy=disable_non_proxied_udp'])
        context=await browser.new_context(viewport={'width':390,'height':1100},device_scale_factor=1,
            service_workers='block',java_script_enabled=site=='yummy',accept_downloads=False,permissions=[])
        await context.route('**/*',route_request)
        await context.route_web_socket('**/*',lambda ws:ws.close())
        page=await context.new_page()
        try:
            await page.goto(url,wait_until='domcontentloaded',timeout=60000)
            if site=='yummy':
                await page.get_by_role('heading',name='Resultados para',exact=False).first.wait_for(timeout=15000)
                try:await page.get_by_text('Cargando productos…',exact=True).wait_for(state='hidden',timeout=20000)
                except Exception:pass
            else:
                await page.locator('h1').first.wait_for(timeout=10000)
            await page.wait_for_function('Array.from(document.images).every(i=>i.complete)',timeout=15000)
            await page.evaluate('document.fonts.ready')
            text=await page.locator('body').inner_text()
            # Anonymous public viewport only. Never fill account or personal fields.
            shots=[]
            for stage in ('page_loaded','results_review'):
                if stage=='results_review':
                    if site=='yummy':
                        await page.get_by_text(results[0]['title'],exact=True).first.scroll_into_view_if_needed(timeout=5000)
                    else:
                        await page.get_by_text('NATALIA JIMENEZ',exact=True).first.scroll_into_view_if_needed()
                image=await page.screenshot(type='jpeg',quality=85,full_page=False,animations='disabled')
                name=f'{site}-{stage}.jpg';(out/name).write_bytes(image)
                shots.append({'stage':stage,'file':name,'source_url':page.url,'sha256':hashlib.sha256(image).hexdigest(),
                              'environment':'live_public_anonymous','sent':False,'partial_render':True})
            if site=='yummy':
                # Open a product title, never cart, contact, favorite or checkout.
                await page.get_by_text(results[0]['title'],exact=True).first.click()
                await page.wait_for_url('**/producto/*',timeout=10000)
                await page.locator('h1').filter(has_text=results[0]['title']).wait_for(timeout=15000)
                await page.wait_for_function('Array.from(document.images).every(i=>i.complete)',timeout=15000)
                image=await page.screenshot(type='jpeg',quality=85,clip={'x':0,'y':0,'width':390,'height':700},animations='disabled')
                name=f'{site}-product_review.jpg';(out/name).write_bytes(image)
                shots.append({'stage':'product_review','file':name,'source_url':page.url,'sha256':hashlib.sha256(image).hexdigest(),'environment':'live_public_anonymous','sent':False,'partial_render':True})
                links=await page.locator('a[href*="/producto/"]').evaluate_all('(links)=>links.slice(0,12).map(a=>({url:a.href,text:a.innerText}))')
                if not results: results=links
            if site=='mitickera':
                parsed=VisibleHTML(page.url);parsed.feed(await page.content())
                results=[x for x in parsed.links if query.casefold() in x['text'].casefold()][:12]
            results=list({r.get('objectID',r.get('url')):r for r in results}.values())[:12]
            report={'site':site,'query':query,'source_url':url,'selected_url':page.url,'observed_at':reader.cache[next(iter(reader.cache))].observed_at if reader.cache else '',
                    'environment':'live_public_anonymous','text':text[:30000],'results':results,
                    'requests':reader.requests,'bytes':reader.total_bytes,'blocked':blocked,'captures':shots,
                    'limitations':['Partial rendering: external resources and non-allowlisted endpoints blocked.',
                                    'Search/listing evidence is not availability, cart, reservation or order.',
                                    'No WhatsApp transport or conversational worker attached.']}
            (out/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2))
            return report
        finally:await context.close();await browser.close()

