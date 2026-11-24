# Only real businesses are visible

Decided 2026-11-23: Sabi shows customers only real, verified businesses — NACIONAL Restaurante,
Bizza and MC Racuchos at decision time. Demo/test businesses stay in the database (nothing is
deleted and the owner panel keeps working for every business), but Sabi must not:

- recommend them or list them in catalog answers (`concierge.recommendations`),
- route a message to them by mention, product match or `[sabi:<slug>]` link (`auth`),
- offer them in city delivery options (`venezuela.covering`),
- serve their public storefront or accept their public checkout (`routers/store`).

The list lives in `app/visibility.py` (`HIDDEN_SLUGS`), on top of the standing convention that
any business named "Prueba ..." is internal. To hide another business, add its slug there; to
show one again, remove it. Data is never deleted by this rule.

Open conversations with a now-hidden business are not stranded: the open-conversation
continuity path still resolves, so an in-flight order can finish.
