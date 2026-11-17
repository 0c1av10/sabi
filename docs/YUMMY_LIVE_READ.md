# Yummy public-source product search

Extends existing shopping inquiry after PR13 and cold-import fix7f9d3cb. No paid provider, new service, account, model or checkout. Other marketplaces remain explicitly unsupported, not silently faked.

## What changes

An explicit Yummy shopping platform plus a product query reads its public catalog, then up to3public product details. A prior laptop query can be resumed by selecting Yummy Marketplace. Known ride words do not route into product search. Generic explicit searches such as "busca cafetera en Yummy Marketplace" also work. Returned links use Yummy's verified product route, never seller-supplied destinations.

The reader reuses the existing reviewed public-source policy: allowed HTTPS hosts/paths and methods, fresh public-DNS validation and pinned TLS, no cookies, proxy, caller headers, credentials, user identity, phone or location. Only the explicit product query leaves Sabi. POST only public search with rebuilt query body; account, contact, cart, order and payment endpoints are rejected. Query80characters;4requests/1MB;4second socket timeout;14second request-start budget;16second response deadline. No retries on source denial, throttling or errors. DNS delay can outlive the response deadline in a background thread, but never sends a user response. No ongoing monitoring.

Source responses are untrusted data. No raw descriptions, seller profiles, instructions, storage tokens or error bodies reach a model or the user. Only bounded title, verified detail price, known product URL and observation time are retained in the transient result. Search candidates must match query tokens, be marked inStock in the listing, and have a matching active/not-paused detail. This is evidence of a publication, not an inventory guarantee. Currency is displayed as the site's "$" symbol, not asserted as USD; total shipping/tax not quoted. Invalid prices, IDs and details are omitted. Failure/empty results do not claim no products exist. If another shopping focus or reset replaces the query during reading, the old answer is suppressed.

## Evidence

Anonymous catalog query laptop dell17Nov2026:
https://yummy-marketplace.com/productos?q=laptop+dell

Frontend title clicked and screenshot inspected,04:02Caracas:
https://yummy-marketplace.com/producto/6acfb8365935ab05a39afee2
Laptop Dell3380 32GBX4GB, $209, conditionNuevo as displayed. Product condition is seller/platform data, not an independent assessment.

New provider code executed separately at08:04:29UTC, statusok, verified details:209,132,600. No real WhatsApp send, no purchase, no model call. Source can change. New link routes for further API verified products are not a checkout or stock confirmation.

Full offline suite288passed after integration with PR14 and PR15; original search suite261passed/3pre-existing baseline failures. Includes clean-process app import, SSRF/destination/method/payload/budget tests, raw-source filtering, malformed prices, rate-limit fallback, durable Dell→Yummy sequence, generic category, ride routing, and stale search suppression after reset. Real-provider read is separate from fake-send dialog tests. Preview health must pass before main. A healthy deployment does not prove WhatsApp delivery or model prose.
