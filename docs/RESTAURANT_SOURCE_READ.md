# Explicit restaurant source read

Adds a useful read path after the unknown-merchant guard. It is not a general web search engine, a merchant integration, an imported menu or a booking system.

Input: an explicit HTTPS website supplied in the current message and an unexpired place/restaurant entity+city already clarified in focus. No cookies, credentials, phone, name or location are sent. Without focus, ask the local/city rather than reading an arbitrary link.

Reads public HTML on the same site. If city is not in page identity headings, discovers one city branch through observed source links, then same-host sitemap and one locations directory if needed. All hops validate HTTPS destination, same site, fresh public DNS, pinned TLS, path restrictions and response content. Userinfo, query strings, IP hosts, local/private DNS, account/cart/order/payment/action paths and cross-site redirects are rejected. XML sitemap parsing rejects declarations/entities. Budget6requests/1MB total,500KB/page,4second socket timeout,12second start budget,15second response deadline. DNS lookup can outlive the response deadline in a thread but cannot send a late response. No polling/retry on denial.

Only source reports are returned, not an assertion of official identity. Entity must match title/h1/h2; city in a banner/review is insufficient. Address and hours are bounded pre-footer excerpts. Raw scripts/descriptions/errors never reach the model or reply. Instruction-like excerpt values are filtered. Scope remains conservative, not universal HTML understanding.

Menu prices are intentionally NOT returned: a branch page can reuse a global menu component. The response says menu/sede scope was not confirmed rather than attaching global prices to a verified address. No hardcoded Beijing identity, branch URL, address, hours, menu, city or phone in application code. No restaurant/order/catalog tables are touched, and stale responses are suppressed if focus changed.

## Real source check17Nov2026

Input supplied by user: https://www.beijingrestaurante.com/es
Reader followed root redirect, sitemap, observed location-directory URL, then observed branch link:
https://www.beijingrestaurante.com/ubicaciones/lecheria

Result: address C.C SEDNAYA. AV. PRINCIPAL DE LECHERIA, DIAGONAL A CASA DANA; hours Domingo a Jueves12PM-11PM; Viernes y Sábados12PM-12AM. Independently read in authenticated browser and visually inspected branch heading. No form, reservation, contact, payment or model call.

Important caught regression: a first extractor accepted root banner mentioning Lechería and grabbed La Tahona address. This was fixed before publication by requiring city in page identity headings and selecting a source branch. Test preserves this case.

Offline suite274passed/3pre-existing baseline failures, including clean-process import and tests for local/private DNS, userinfo, query leakage, action paths, cross-site redirect, wrong identity/city, banner-not-branch, sitemap navigation, source-instruction filtering, exact focus and stale response. This is not WhatsApp E2E. Source may change or misstate its own facts. Preview startup must be checked separately before production activation.
