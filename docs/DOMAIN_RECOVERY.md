# Recovering a cinema conversation

A response-format instruction accidentally stored as a place is ignored when read. This applies only to the known invalid format-command shape. It does not erase all old conversations or repair names.

An explicit cinema request takes priority over an older restaurant/place topic. "De los cines" is a cinema request, not a merchant name. When the cinema response asks for a city, the next "PLC" is treated as Puerto La Cruz in that conversation. Without that cinema context, the abbreviation is not treated as a confirmed city. "Qué hay para ver en PLC" asks for confirmation instead of silently assuming.

"Aló, Puerto La Cruz" can answer a pending cinema-city question without restarting the greeting. A complaint about not being understood keeps the cinema task and its city instead of repeating the welcome.

The city is passed into the cinema query and retained across those turns. This is context recovery, not proof of current showtimes. The existing cinema source checks still have to verify city, venue, date and time. No purchase or reservation is made by this recovery.

## Scope

This change does not provide a national city directory, geocoding, geographic filtering for shopping/gym/events, or verified showtime coverage for Puerto La Cruz. It does not repair previously stored names. The isolated replay uses a replacement cinema answer, so it verifies routing and city propagation, not a live provider response or WhatsApp delivery.
