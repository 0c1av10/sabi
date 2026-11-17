# Conservative name recognition

This change is preventive. It does not repair Contact rows or verify a person's legal identity.

Explicit introductions remain accepted: Me llamo Ana, Mi nombre es Carlos Pérez, Soy Ana, quiero pedir, and Hola soy Maria y quiero una clase. The parser requires a complete short introduction or an explicit new clause instead of taking the first few words of a longer sentence. Common role, health, time and conversational terms are rejected. Examples that previously became stored names include Soy entonces del cine, Llámame mañana and Soy alérgico al maní.

A profile display name remains a fallback marked profile, only when no name is stored. It is not verified identity and cannot overwrite a user-stated name. Each phone retains its own row. Previously stored names, including Entonces, are not hidden or rewritten by this change. A separately authorized, exact-phone compare-and-set repair remains a distinct operation.

This is conservative deterministic parsing, not a complete linguistic or identity system. It may miss unusual names or ambiguous introductions; it must not be described as guaranteeing everyone's real name. No paid model or new service is used.

Validation: 312 tests passed, 3 existing baseline failures in Bizza/events remained. New cases cover ambiguous introductions, clear introductions, persistence, profile source marking, per-phone isolation and legacy-name preservation. No WhatsApp send or production database mutation was used.
