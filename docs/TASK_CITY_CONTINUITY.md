# Explicit city for a restaurant query

A task city is an explicit city used for the current query. It is not a home address, GPS fix, or permanent preference. The focus expires after 30 minutes.

## Behavior

- Repeating the same place or asking for another response format keeps an already declared city.
- A statement such as "Estoy en Valencia", "Mejor en Valencia", or "Ahora en Caracas" updates the task city.
- Changing city preserves the named place but drops its old restaurant-catalog scope. A follow-up cannot reuse that restaurant's menu or delivery from a different city.
- If no city-specific source is verified, Sabi says so and asks for an official link rather than inventing local options.
- A different named place does not automatically inherit the previous place's city. A city supplied before naming any place can apply to that first place.
- Format instructions such as "Mándamelo en tres mensajes" are not cities.

## Limits

The parser accepts a small set of explicit city phrases. It does not validate place names against a geographic database. An address or a sentence mixing several requests may need clarification. While a city question is pending for an unresolved place, a bare short answer ("Lecheria") is taken as that city; see docs/CONVERSATION_CONTINUITY.md.

Saving a city does not add geographic search, city coverage, local availability, or verified branch-specific prices. Yummy, shopping, cinema, gym and events do not gain geographic filtering from this change. A city statement in those tasks records the city and warns that filtering is not verified; their later domain-specific search still requires separate geographic validation.

Existing bad names and stored focus rows are not repaired. An old task can expire or be explicitly restarted.
