# Anonymous public web reads (not deployed)

Adds to existing Sabi, does not replace food/events/gym/Rides. Everything is OFF
by default. No live WhatsApp messages, merchant accounts, carts or payments used.

## Verified from code on 17 November 2026

- `python pilot/web_public_read.py yummy audifonos OUTPUT`: real Chromium search
  at https://yummy-marketplace.com/productos?q=audifonos , 12 public hits, photos,
  displayed prices and a public product page opened through its own title.
  No BUY, Chat, favorite, quantity or checkout control touched.
- `python pilot/web_public_read.py mitickera natalia OUTPUT`: actual catalog HTML
  and rendered viewport at https://www.mitickera.com/eventos/ . Catalog has old
  events. A COMPRAR link is not proof of a future event or live inventory.
- Mercado Libre anonymous listing returned HTTP 403. No retry or bypass. Connector
  is NOT considered working and manual CLI execution for it remains disabled.
- Worker generates bounded viewport JPEGs, source URLs, timestamps, hashes, read
  evidence and limitations. Partial rendering is explicit because analytics and
  unrelated resources are blocked. Product excerpt avoids public seller profile.
- 41 further offline tests: public destination/DNS policy, bounded search body,
  account/commitment endpoint rejection, queue, private claims, image size,
  no-send behavior and signed inbound webhook -> durable job. Whole suite 165
  pass with the same 3 pre-existing failures. This is not a green suite.

## Network and privacy

No user profile/cookies/login. Requests are fulfilled only through PublicReader:
HTTPS host/path allowlist, fresh DNS validation of ALL records, IP-pinned TLS and
peer verification, no proxies/caller headers/cookies, explicit checked redirects,
byte/request/time budgets. Third-party analytics blocked. WebSockets and service
workers blocked. Yummy's public search is the ONLY allowed POST, using a rebuilt
fixed query body. Only search page 0 and a bounded hit count are allowed.
Related searches with different queries are rejected. Public media access is
limited to its observed product buckets, not all Google storage.

This is application-level isolation, not a full OS egress sandbox. Production
needs a dedicated worker network policy, read-only filesystem and process limits.
No claim of arbitrary-web safety. Site text remains evidence, never instructions.
Public catalog responses can be stale or misleading: show source/time and do not
promise availability or authenticity based on a listing. Never transmit raw
provider responses, storage tokens or seller details to the dialog model.

## Additive dialog connection (implemented, disabled)

`/web yummy audifonos` or `busca audifonos en yummy marketplace`; same for
MiTickera. Explicit syntax avoids stealing restaurant/event/Rides traffic.
Authenticated inbound -> separate PublicWebJob, server-owned phone/site/query ->
private worker claim -> bounded public capture -> result for that same job.
Delivery is separately OFF; even queue acknowledgments do not send with it off.
Claims expire, duplicate inbound IDs do not create duplicate work, one active
job per phone, daily cap, ambiguous send stays needs_review and never auto-retries.
No image persistence or public evidence endpoint. No automatic job dispatch.

Manual pull entry: `pilot/public_web_pull.py`, takes approved Sabi HTTPS host and
private worker credential via environment. Temporary captures are deleted when
it finishes. NEVER print secret environment values. Separate config:
PUBLIC_WEB_PILOT_ENABLED=false; PUBLIC_WEB_DELIVERY_ENABLED=false;
PUBLIC_WEB_ALLOWED_PHONES empty; PUBLIC_WEB_WORKER_TOKEN empty.
No workflow, cloud service, new credential or live settings were created.

## Activation gap

Vercel API dependencies do not contain Playwright/Chromium. Pick and approve an
actual worker host before enabling queues. Existing Rides Actions runner and
phone credits are not used. Adding a new workflow requires a separately scoped
credential and explicit cost/runtime review. Deployment, credentials, worker
setup and live WhatsApp remain gated; do not enable a queue with no worker.
A serverless webhook response is not a durable Chromium execution host.

Before activation: use an OS-isolated worker, establish cost cap/cleanup, verify
expiry and concurrent claims on the target DB, private result retention, current
provider billing and visible delivery for the one permitted phone, preserve all
existing behaviors, and retain rollback. Read-only tasks do not authorize carts,
merchant logins, messages to sellers, bookings, purchases or payments.

## Verified host proposal (no service created)

Current Render account: Hobby, one existing service; no self-hosted GitHub runner
registered. Propose separate Render 1 CPU/2GB worker at $25/month compute,
prorated, initially one day then stop/delete, no disk/new DB. Bandwidth/workspace
and any extras remain subject to final confirmation before creation. 512MB at
$7/month is not assumed enough for Chromium. Existing promo credits are money,
not authority, and were NOT used. Separate approval must cover them and any cap.
Do not assume deleting code or turning a feature flag off stops host billing.

Render worker model and pricing verified:
https://render.com/docs/background-workers
https://render.com/docs/compute-plans
https://render.com/pricing

GitHub standard public-repository compute is free, but Actions terms restrict
application/serverless service use. It is not recommended as Sabi's production
worker, only bounded software tests. A new manual workflow also needs to exist
on the default branch and needs permissions outside current token scope.
https://docs.github.com/en/billing/concepts/product-billing/github-actions
https://docs.github.com/en/site-policy/github-terms/github-terms-for-additional-products-and-features
https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows
