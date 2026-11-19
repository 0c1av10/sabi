# Cinema reactions and processing status

Prepared for review, not enabled in production.

## Cinema

Use 🎟️ for cinema, showtimes and film requests. It takes priority over generic food/order words such as "quiero". Thanks and complaints retain their own reactions. No random alternative is selected. 🎬 remains an accepted future alternative, not an automatic rotation.

## Processing

Do not use 🧠 merely because a message contains the word "thinking". Show it only for work that has actually started and remains pending beyond a chosen delay. The proposed delay is 8 to 10 seconds, subject to review. Cancel the timer if the answer finishes sooner. A status reaction is not proof that a lookup succeeded.

Terminal behavior:

- Success: replace 🧠 with 🎟️ for a cinema request; remove it for a request with no final reaction.
- Error or cancellation: remove 🧠; send a truthful failure or cancellation result through the normal response path.
- Process crash: recover a persisted cleanup record and remove the stale status. Do not depend only on a finally block.
- Uncertain removal: mark cleanup pending. Provider acceptance does not prove the recipient sees the change.

The current proposal prepares the cinema rule and a Zernio removal transport, tested with mock HTTP only. It does not enable 🧠, delayed notices, background searches, jokes, or games. Processing status needs durable per-request identity, conversation/message destination, terminal state and cleanup recovery before activation. Newer messages must not change the target of an older request's cleanup.

## Provider contract

Zernio documents one WhatsApp reaction per sender per message. Add uses POST; removal uses DELETE on the message reactions endpoint with accountId in the query. Removal affects our own reaction, not the other participant's. A successful response indicates request acceptance, not guaranteed visible placement or removal.

Source checked 17 November 2026: https://zernio.com/openapi.yaml . No real reaction was sent or removed to verify this proposal.

## Waiting entertainment

A short waiting notice can be considered separately. Offering a game while a search continues requires a durable search job and a side conversation that cannot overwrite the primary task. Do not offer parallel play until that behavior is implemented and tested. No provider cost or message allowance has been verified for this extension.
