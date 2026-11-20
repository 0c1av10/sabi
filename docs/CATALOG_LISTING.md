# Catalog listing

Reported 2026-11-20: "Dame todos los restaurantes que tengas" returned two random businesses,
and the list changed on every ask.

## Behavior

- A request for the whole catalog ("todos los restaurantes", "qué restaurantes tienes",
  "la lista completa de locales") returns every registered business in stable order, never a
  sample.
- Ordinary open-ended asks ("tengo hambre", "quiero un plan") still get one or two varied
  suggestions, so Sabi recommends instead of dumping the catalog.
- Internal test businesses ("Prueba ...") are never listed.

## Limits

- The catalog is not geographically filtered: the list is presented with the standing caveat
  that location and availability for the person's zone are unconfirmed.
- Businesses registered as demos in a production database are data, not code: removing them
  from the catalog is an operator decision, not something the listing logic infers.
