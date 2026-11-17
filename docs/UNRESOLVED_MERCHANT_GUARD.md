# Unknown merchant must not inherit another catalog

Production regression observed17Nov2026 after PR13/cold-start fix7f9d3cb. A query for an unknown named restaurant in a city selected another restaurant because its menu contained that city's name as a product suffix. This was not the earlier cinema failure.

Public source https://sabi-api.vercel.app/api/store/nacional has Cachapa Lechería. Previous product matcher accepted one isolated suffix token, so "De Beijing en lechería" matched Nacional. The greeting closed the old restaurant conversation; product matching could still pick the wrong merchant afterwards.

Fix is generic, no Beijing catalog or special-case name:
- Recognize explicit place references, ask about the unrecognized entity, retain city as location only.
- Remove "en CITY" from product scoring, and require a leading-product or category match rather than an isolated flavor/suffix.
- An old open conversation is not enough authority to reuse its tenant: current unexpired restaurant focus must name the same merchant.
- Unknown place focus stops old restaurant fallback. Known business names and [sabi:slug] links retain their routes.
- No order, item, history or contact-name data are erased or rewritten by this change.

Validation221passed/3pre-existing baseline failures, including clean-process app import. New regressions include live-catalog-shaped Cachapa Lechería collision, current/missing/wrong-domain focus, unrelated unknown businesses, Hola→unknown-place sequence, known Bizza/tag/pizza, and preservation of an open conversation's state/status without creating an order. These are offline routing tests with outbound/model blocked, not production WhatsApp E2E. Preview health must pass before main.

Known limit: deterministic place phrases are conservative; they are not universal named-entity recognition. Stored corrupt contact name remains a separate data repair requiring exact account scope and confirmation, not a blacklist in greeting code. Website/menu discovery and product search changes are not part of this patch.
