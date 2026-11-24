# A greeting restarts the conversation

Reported 2026-11-23: "Habla sabi" was not in the greeting lexicon, so with an open NACIONAL
conversation it was routed into that business and answered as a continuation of the old food
order (offering pollo a la brasa, cachapa...) instead of asking what the person wanted.

## Behavior

- The greeting lexicon covers the usual openers: "hola"/"oli"/"ola", "habla", "habla sabi",
  "epa", "épale", "aló", "oye", "qué tal", "qué hay", "buenas...", "buenas buenas", "saludos",
  "hello"/"hey", and a bare "sabi", with any case or punctuation ("Buenas noches, Sabi").
- Greeting-only small talk ("hola, ¿cómo estás?") also restarts. A greeting followed by a
  request ("Habla sabi, quiero pizza") is not a bare greeting: the normal routes answer the
  request, so an explicit petition is never swallowed by the restart.
- A message that is only a greeting restarts: open restaurant conversations are closed and Sabi
  answers by asking what the person wants today ("¿Qué te provoca hoy: comer algo, salir o
  tienes otro plan?"). It never greets and then keeps pushing the previous order.
- A greeting followed by a request ("habla, quiero pizza") is not a bare greeting and keeps the
  normal routes.
- Memory is kept: the person's name, saved preferences and the message history are not touched.
  Only the *open conversation* state (which business the chat is "inside") is reset.
- The cinema session keeps its own approved rule: a greeting with an active cinema task answers
  "Seguimos con cine..." instead of restarting (see docs/CINEMA_REACTION.md era behavior). If
  that should also restart, it is a separate product decision.

## Name guard

- A stored contact name equal to a catalog business or its slug ("Tastio", "Bizza") is never
  used to address the person: the greeting falls back to no name. The stored record is not
  modified; "me llamo Octavio" or "olvídame" still correct it. This covers names saved by
  mistake while roleplaying as a demo business.

## Limits

- An abandoned open conversation still captures ambiguous non-greeting messages by design
  (docs/CONVERSATION_CONTINUITY.md). Only greetings, domain switches and resets break out of
  it. A time-based expiry of open conversations is an open product decision, not part of this
  change.
