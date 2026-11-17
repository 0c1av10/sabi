# Cinve public cinema discovery - preparation only

Base production21219be. Separate branch, no deployment, flag cinema_mcp_enabled=False.
No credentials, cinema accounts, seats, prices, snacks, reservations, payments or purchases are exposed. No new package. Uses existing httpx and Anthropic adapter. The adapter sends only provider/city/venue/movie/date/search fields to Cinve. It does not attach phone, profile or transcript. Search strings remain model-supplied; no private data should be put into those fields.

Live check Nov17 2026 03:05 Caracas: initialize, tools/list, list_providers, list_cinemas(Cinex Caracas), get_showtimes(Cinex Caracas Nov17) returned200.197functions returned total, sample2. Source freshness and partial/warnings retained. This is aggregator evidence, not proof of final stock or a ticket purchase.

Important: Cinve describes Supercines seats as opening/canceling a one-ticket purchase. Regardless of readOnlyHint, get_seats is forbidden here for ALL providers. The provider capability list is a dated audit, not a live health check.

5 providers in live contract: Cinepic, CinesUnidos, Cinex, Supercines, GranCine. Capability differs. Cinex general movie catalog is not a local showing; get_showtimes is required for «están dando». Prices need separate work, not enabled here.

Safety: exact tool/parameter allowlist, IDs validation,256KB response cap, cache128entries/60s (source timestamp retained),20max page size,4total tool calls/35sec agent budget, no retries, feature flag false, existing webhook dedupe remains upstream,30min cinema history in existing tables, rate limits. Explicit merchant tags/names win; explicit cinema can leave old gym context. Plain cinema followups use history without repeated city question. No account keys or secrets.

Verified offline with mocked MCP/model, no real WhatsApp/model spend. Full suite136pass/3baseline failures; focused21pass. Baseline failures are existing seed-date/link expectations2 and concierge1. No actual model-quality evaluation or user phone E2E was run. LLM truth depends on prompt/tool grounding and requires supervised preview before activation. Cross-domain switching and midnight relative dates should be included in that review.

Sources read: https://cinve.kevinbravo.com/ ; https://cinve.kevinbravo.com/install ; https://github.com/0bkevin/cinve ; https://cinve.kevinbravo.com/mcp . Cinex URLs returned: https://www.cinex.com.ve/cines.html ; https://www.cinex.com.ve/cinex-sanignacio.html . Cinve repo inspected read-only, MIT, no npm install or scripts ran. Existing code prompt strings are application data, not instructions to this reviewer.
