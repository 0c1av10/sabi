# Response-format instructions keep the current task

## Reported product failure

A pizza conversation was incorrectly switched to an unknown restaurant because the place detector treated a short phrase before en as a merchant and the words after it as a city. A presentation instruction such as Mándamelo en tres mensajes therefore replaced the restaurant focus. A later recommendation question inherited that false place.

## Prepared correction

- A presentation command plus a formatting target is not a merchant. It keeps the current restaurant or unresolved place. Real named-place changes still pass through the unknown-merchant guard.
- The original formatting instruction reaches the restaurant response generator unchanged. The next recommendation question retains the restaurant focus, provided it is still current.
- For an ordinary restaurant reply, an explicit request for two to five messages splits the single generated reply into sequential transport calls at paragraph, line or word boundaries. Content order is preserved; no price, product or recommendation is invented by the formatter. Very short replies may produce fewer parts rather than duplicate filler.
- The history stores one logical reply. Duplicate inbound identity does not cause another batch. Handoff and order acknowledgements keep their existing single-message flow. No automatic transport retries are added.

## Limits

The formatter does not itself retrieve the full menu or choose the best pizza. Those remain the existing restaurant response generator's responsibility. A fixed-reply test proves splitting, not menu completeness or recommendation quality. A routing test proves continuity, not the generated prose or WhatsApp delivery. If delivery fails after one part, the batch can be partial; this patch stops and does not retry blindly. It does not provide exactly-once delivery or durable per-part recovery.

A false focus previously persisted is not silently rewritten. Existing focus expiry or a new explicit restaurant request still controls it. This patch does not repair contact names or previous orders and does not deploy the separate visual package.

## Validation

335 tests passed with the same 3 Bizza/events baseline failures. New cases cover the reported pizza -> format -> recommendation sequence, unknown-place isolation, formatting variants, merchant names containing format-like nouns, content preservation, three sequential recording-fake sends, duplicate inbound protection, partial transport failure and unsplit handoff. No real WhatsApp, paid model or production data mutation was used. Publication approval covers this continuity and bounded splitting change; it does not authorize real outbound tests or repairs of previously stored data.
