# Review packet: Sabi quality corrections, 17 November 2026

Preparation only. No production claim. Built from main95db7b6, includes PR11 code and corrections for name, cuisine, vocative and task boundaries, but NOT PR10/new focus table or external search.

## Evidence and scope
Same real router + SQLite harness on baseline/current: docs/evidence/quality-before.json and quality-after.json. Model call replaced before invocation; outbound replaced by recording fake. This is a deterministic routing/state/data test, NOT evidence of improved live model prose.

Baseline stores Entonces from an imperative, then addresses user that way, routes Sabi/marketplace/laptop to cinema, and picks a criollo tenant for Chinese. Candidate keeps an explicitly supplied synthetic name Ana, vocative does not search, explicit cuisine cannot be overridden by product/old tenant fallback, marketplace asks which platform and Dell request does not invent price/platform. Existing contacts are not altered: no blacklist hiding a name and no inferred name repair.

Varied natural cuisine tests cover Chinese, Japanese/sushi, Italian, Arab, Venezuelan, Mexican, Peruvian; unknown/multiple/negative cuisine asks clarification rather than random substitute. Descriptive rica/sabrosa/saludable is not mistaken for nationality. Catalog tag evidence is not independent live verification, and no new merchant/menu is fabricated. Existing Italian menu-specific check preserved. This remains a bounded parser, not general semantic understanding or model training.

Cinema continuation now requires an active session AND bounded follow-up form instead of treating all messages as cinema. Explicit cinema returns to cinema. Other current topic wins over stale cinema session. Unknown free text is no longer sent to cinema solely because of a 30min session. This can lose some unsupported elliptical movie-title replies; the correct future fix is selected entity/task state, not another keyword blacklist.

PR11 logic integrated: hours use recorded field before paid model call; unknown hours are honest. Guard prevents unverified handoff action from locking a conversation and does not block legitimate 'te paso el menú'. Identity remains Sabi, not an employee of the merchant.

## Not solved
General web/product search, Abruzzo discovery, broader preference learning, persistent entity/task schema, safe repair of already-contaminated database names, live model answer validation, current hours/menu/source freshness. Existing last_topic used for shopping task text is bounded but not a structured multi-task memory. No model fine-tune, API spend, new provider, recurring jobs, new table, outbound tests or deployment.

## Review before activation
Review compatibility with PR10, race/parallel user turn effects and expiry of old focus/task information. Verify general inquiry fallback and selected-item semantics; do not announce complete shopping or place search. Three known pre-existing full-suite failures remain, not silently accepted as passing coverage. EvalsPR6 and daily cinema MarkdownPR8 remain separate preparations.
