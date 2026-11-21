# Venezuelan city knowledge

`backend/app/venezuela.py` holds a gazetteer of Venezuelan cities: the capital of every state and
Distrito Capital, the Anzoátegui north coast where current merchants deliver, and other cities
customers commonly name. Each entry has its state and the ways people write it on WhatsApp
(`lecheria`, `PLC`, `Ccs`, `Bqto`, `Pto Ordaz`, `margarita`). Matching ignores case and accents.

## Behavior

- A city a customer names is stored with its canonical spelling ("Lecheria" → "Lechería", "plc" → "Puerto La Cruz"). Unknown places are kept as written.
- "Quiero comida en Lechería", "En lechería que me recomiendas" → "comida", and "Estoy en Lechería" list the catalog businesses whose **own delivery zones** include that city, with the zone fee. A city no business registered keeps the existing "no verified geographic filter" reply.
- Naming one of those businesses right after keeps the city on the order task.
- A delivery zone written another way ("Delivery a PLC", an address in "lecheria") selects the registered zone.

## Limits

The gazetteer only recognizes names; it never says a business serves a city. Coverage comes only
from delivery zones the merchant registered in the panel. Taglines, websites and neighboring cities
are not coverage. No external restaurant directory is included: restaurants outside the catalog are
still answered with the "no verified source" replies.
