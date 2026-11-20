# Conversation continuity with a business

Reported 2026-11-20: after about 30 minutes without writing, a message like "Si dame ese pero
pídelo mañana a las 9 am" fell back to the welcome and the open order was lost; short follow-ups
("Nacional", "Lecheria", "Agrégale un refresco") were answered with a bare "¿Me repites, por
favor?", which reads as if Sabi had no memory and asked people to repeat themselves.

## Behavior

- An open conversation keeps its restaurant regardless of the 30-minute focus window. The focus
  (`docs/TASK_CITY_CONTINUITY.md`) still governs topic, city and place memory; the conversation
  itself carries which business the person is talking to. Follow-ups such as "Sera delivery" or
  "Agrégale un refresco" stay with that business.
- Only an active unresolved-place task, another live domain (cinema, shopping, gym, events)
  or an explicit full-catalog ask (docs/CATALOG_LISTING.md) outranks the open conversation. A bare greeting ("hola") still closes open conversations and
  restarts, and "olvida el contexto" / "olvídame" still reset.
- The first message routed to a business is answered with the knowledge that the person may be
  continuing a general conversation with Sabi. The last general topic travels with the handoff,
  including the actual businesses Sabi just offered ("recomendación de locales: ..."), so a
  short "Y nacional?" is read against what the person just saw, never in a void.
- An ambiguous "ese / esa" referring to several options Sabi just offered is clarified
  ("¿Cuál de estos: A o B?"), never resolved by picking one. When only one option was offered,
  "ese" means that one. Everything else in the draft (type, zone, address, notes) is kept.
- A requested delivery date or time ("pídelo mañana a las 9 am") is preserved verbatim in the
  order notes. There is no scheduling field yet: the time is information for the owner, not a
  scheduled dispatch.
- When the model returns nothing usable, Sabi answers with a grounded offer (what the business
  sells, menu or a recommendation) instead of asking the person to repeat their message.
- After Sabi asks "¿En qué ciudad queda X?" for an unresolved place, a bare short reply
  ("Lecheria") is taken as the answer to that question. A restaurant mention, a food word, a
  greeting or a service word (menu, precio, delivery, ...) is never taken as a city.

## Limits

- Stickiness follows the most recently updated open conversation. A person who never says "hola"
  or "olvida el contexto" stays with that business until one of the outranking routes applies.
- The general concierge exchange before choosing a business travels as the current topic in the
  model context; it is not stored as restaurant chat history, and the topic field is short (80
  characters), so a long offered list may be truncated.
- Why the model sometimes returned an empty reply in production is not proven by the offline
  tests (they simulate the model); what is verified is that an empty reply can no longer reach
  the client as a bare request to repeat, and that the context the model receives now includes
  the general conversation topic.
- The bare-city binding applies only while a city question is pending for an unresolved place;
  it does not validate the answer against a geographic database.
