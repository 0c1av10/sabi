# Recovering a cinema conversation

A response-format instruction accidentally stored as a place is ignored when read. This applies only to the known invalid format-command shape. It does not erase all old conversations or repair names.

An explicit cinema request takes priority over an older restaurant/place topic. "De los cines" is a cinema request, not a merchant name. When the cinema response asks for a city, the next "PLC" is treated as Puerto La Cruz in that conversation. Without that cinema context, the abbreviation is not treated as a confirmed city. "Qué hay para ver en PLC" asks for confirmation instead of silently assuming.

"Aló, Puerto La Cruz" can answer a pending cinema-city question without restarting the greeting. A complaint about not being understood keeps the cinema task and its city instead of repeating the welcome.

The city is passed into the cinema query and retained across those turns. This is context recovery, not proof of current showtimes. The existing cinema source checks still have to verify city, venue, date and time. No purchase or reservation is made by this recovery.

## Scope

This change does not provide a national city directory, geocoding, geographic filtering for shopping/gym/events, or verified showtime coverage for Puerto La Cruz. It does not repair previously stored names. The isolated replay uses a replacement cinema answer, so it verifies routing and city propagation, not a live provider response or WhatsApp delivery.

## Returning welcome

For a new bare greeting, the approved returning welcome is:

"Hola de nuevo, {nombre}. ¿Cómo te puedo ayudar hoy? ¿Quieres comer o se te antoja ir al cine?"

A doubtful name is omitted from the greeting without changing the saved record. A bare greeting during an active cinema query keeps the city and task instead of restarting this welcome. There is no random rotation among the three drafts.

## Empty answer after cinema discovery

Venue discovery is not a showtime lookup. Once discovery has returned a venue, a small part of the existing query budget is reserved for showtimes. If synthesis returns no text, the recovery can consult a verified venue returned by discovery, only where its city is explicit in the query context. It can read the official Plaza Mayor page when that discovered venue is in explicitly requested Lechería.

The recovery does not increase the configured maximum number of public queries or call a paid model again. Only future functions with a coherent venue and date enter the data-only answer. A paginated response is labelled as part of the showtimes, not a complete billboard. A directory entry from another city does not authorize a local recommendation.

This still needs a real WhatsApp journey check after deployment. Synthetic model replies verify the control flow without using paid inference; separate live public reads prove source availability only.
