# Clarifying a recommendation with a city

Prepared locally for review. Not published.

"What do you recommend?" does not by itself mean food. When the current task is unclear, a question such as "En Lechería, ¿qué me recomiendas?" asks whether the person wants food or a cinema plan, keeping the city rather than asking it again.

An active cinema task can use that localized follow-up as a cinema query and pass the explicit city to its existing source checks. An expired cinema task does not silently decide the meaning of a new recommendation question. The recognized phrase pattern is narrow; it is not a national place-name database or a general language classifier.

If the person answers the clarification with cinema, keep the city and use the cinema flow. If they choose food, do not offer random catalog businesses as verified local options: explain when a geographic filter is missing and ask for a named place or official source. This behavior applies to this clarification flow; it does not add geographic filtering throughout the food catalog.

Food suggestions use neutral wording rather than an automatic "¡Uy, qué rico!". A doubtful saved name is not inserted into the reply. The saved contact itself is not edited.

Testing uses disposable records and replacement cinema answers. It checks routing, city propagation, clarification and name omission, not real WhatsApp delivery, model quality, verified local restaurant coverage or a live cinema result.

## Wider review

The candidate also tests city-before and city-after recommendation phrases, explicit food switches to another city, negated domain requests, expired and active cinema context, and leaving the clarification for a named place or another task. Negated cinema/food requests are clarified instead of guessing which clause wins.

The shared presentation-name function now filters doubtful names for concierge, restaurant-model context, event-model context and gym greeting. It does not rewrite stored records, redact old histories, sanitize every model response, or change a name explicitly entered in the gym registration form.

Generic food catalog suggestions omit unverified taglines and state that location and local availability are not confirmed. Recognized city-qualified food recommendations do not emit random catalog suggestions. This is not source-based geographic filtering: merchant-specific ordering, unusual location phrases, provider data and free-form model replies still need separate review. A catalog disclaimer must not be mistaken for verified local availability.
