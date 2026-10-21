-- Sabi · asistente de eventos (demo FC Producciones). Mirrors backend/app/event_models.py.
-- Access model: the FastAPI backend connects as `sabi_backend`, which owns these tables.
-- RLS is enabled and the Data API roles (anon / authenticated) get an explicit deny-all
-- policy, so nothing is readable or writable from the browser with a Supabase key.
-- Admin authentication lives in the backend (allowlisted emails + signed session cookie),
-- not in Supabase Auth; the service role key must never reach the frontend.

CREATE TABLE IF NOT EXISTS events (
	id SERIAL NOT NULL,
	slug VARCHAR(120) NOT NULL,
	name VARCHAR(200) NOT NULL,
	artist VARCHAR(200) NOT NULL DEFAULT '',
	city VARCHAR(100) NOT NULL,
	venue VARCHAR(200) NOT NULL DEFAULT '',
	starts_at TIMESTAMP WITHOUT TIME ZONE NOT NULL,           -- UTC
	timezone VARCHAR(60) NOT NULL DEFAULT 'America/Caracas',   -- IANA zone used for display
	description TEXT NOT NULL DEFAULT '',
	image_url VARCHAR(500) NOT NULL DEFAULT '',
	status VARCHAR(20) NOT NULL DEFAULT 'borrador'
		CHECK (status IN ('borrador', 'publicado', 'cancelado', 'finalizado')),
	active BOOLEAN NOT NULL DEFAULT TRUE,
	purchase_url VARCHAR(500) NOT NULL DEFAULT '',             -- verified official link; '' disables purchase
	is_demo BOOLEAN NOT NULL DEFAULT FALSE,
	created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT (now() AT TIME ZONE 'utc'),
	updated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT (now() AT TIME ZONE 'utc'),
	PRIMARY KEY (id)
);
CREATE UNIQUE INDEX IF NOT EXISTS ix_events_slug ON events (slug);
CREATE INDEX IF NOT EXISTS ix_events_city ON events (city);
CREATE INDEX IF NOT EXISTS ix_events_status ON events (status);

CREATE TABLE IF NOT EXISTS event_zones (
	id SERIAL NOT NULL,
	event_id INTEGER NOT NULL REFERENCES events (id),
	name VARCHAR(120) NOT NULL,
	price_minor INTEGER NOT NULL CHECK (price_minor > 0),       -- integer cents, never floats
	currency VARCHAR(3) NOT NULL DEFAULT 'USD' CHECK (currency IN ('USD', 'EUR', 'VES')),
	availability VARCHAR(20) NOT NULL DEFAULT 'por_confirmar'
		CHECK (availability IN ('disponible', 'agotado', 'por_confirmar')),
	verified_at TIMESTAMP WITHOUT TIME ZONE,
	PRIMARY KEY (id)
);
CREATE INDEX IF NOT EXISTS ix_event_zones_event_id ON event_zones (event_id);

CREATE TABLE IF NOT EXISTS event_sessions (
	id VARCHAR(36) NOT NULL,
	channel VARCHAR(20) NOT NULL DEFAULT 'web',
	state_json TEXT NOT NULL DEFAULT '{}',
	created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT (now() AT TIME ZONE 'utc'),
	updated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT (now() AT TIME ZONE 'utc'),
	PRIMARY KEY (id)
);

CREATE TABLE IF NOT EXISTS event_messages (
	id SERIAL NOT NULL,
	session_id VARCHAR(36) NOT NULL REFERENCES event_sessions (id),
	role VARCHAR(10) NOT NULL,
	body TEXT NOT NULL,
	created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT (now() AT TIME ZONE 'utc'),
	PRIMARY KEY (id)
);
CREATE INDEX IF NOT EXISTS ix_event_messages_session_id ON event_messages (session_id);
CREATE INDEX IF NOT EXISTS ix_event_messages_created_at ON event_messages (created_at);

-- A prepared selection is NOT a reservation.
CREATE TABLE IF NOT EXISTS event_selections (
	id VARCHAR(36) NOT NULL,
	session_id VARCHAR(36) NOT NULL REFERENCES event_sessions (id),
	event_id INTEGER NOT NULL REFERENCES events (id),
	zone_id INTEGER NOT NULL REFERENCES event_zones (id),
	quantity INTEGER NOT NULL CHECK (quantity > 0),
	unit_price_minor INTEGER NOT NULL,
	subtotal_minor INTEGER NOT NULL,
	currency VARCHAR(3) NOT NULL,
	created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT (now() AT TIME ZONE 'utc'),
	PRIMARY KEY (id)
);
CREATE INDEX IF NOT EXISTS ix_event_selections_session_id ON event_selections (session_id);
CREATE INDEX IF NOT EXISTS ix_event_selections_event_id ON event_selections (event_id);

-- Analytics: interest | selection | click | payment_reported | human_request.
-- A click only means the official link was opened; it is never a sale.
CREATE TABLE IF NOT EXISTS event_activity (
	id SERIAL NOT NULL,
	session_id VARCHAR(36) REFERENCES event_sessions (id),
	event_id INTEGER REFERENCES events (id),
	zone_id INTEGER,
	selection_id VARCHAR(36),
	kind VARCHAR(20) NOT NULL
		CHECK (kind IN ('interest', 'selection', 'click', 'payment_reported', 'human_request')),
	detail TEXT NOT NULL DEFAULT '',
	created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT (now() AT TIME ZONE 'utc'),
	PRIMARY KEY (id)
);
CREATE INDEX IF NOT EXISTS ix_event_activity_session_id ON event_activity (session_id);
CREATE INDEX IF NOT EXISTS ix_event_activity_event_id ON event_activity (event_id);
CREATE INDEX IF NOT EXISTS ix_event_activity_kind ON event_activity (kind);
CREATE INDEX IF NOT EXISTS ix_event_activity_created_at ON event_activity (created_at);

-- "Ya pagué" reports. Only an authenticated admin moves a report to `confirmed`,
-- recording who reviewed it, the reference, amount and currency.
CREATE TABLE IF NOT EXISTS event_purchase_reports (
	id SERIAL NOT NULL,
	session_id VARCHAR(36) NOT NULL REFERENCES event_sessions (id),
	selection_id VARCHAR(36),
	event_id INTEGER REFERENCES events (id),
	user_reference VARCHAR(160) NOT NULL DEFAULT '',
	status VARCHAR(12) NOT NULL DEFAULT 'reported'
		CHECK (status IN ('reported', 'confirmed', 'rejected')),
	created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT (now() AT TIME ZONE 'utc'),
	reviewed_by VARCHAR(200) NOT NULL DEFAULT '',
	reviewed_at TIMESTAMP WITHOUT TIME ZONE,
	confirmed_reference VARCHAR(160) NOT NULL DEFAULT '',
	confirmed_amount_minor INTEGER,
	confirmed_currency VARCHAR(3) NOT NULL DEFAULT '',
	note TEXT NOT NULL DEFAULT '',
	PRIMARY KEY (id),
	CHECK (status <> 'confirmed' OR (reviewed_by <> '' AND confirmed_amount_minor IS NOT NULL
	                                 AND confirmed_currency <> '' AND confirmed_reference <> ''))
);
CREATE INDEX IF NOT EXISTS ix_event_purchase_reports_session_id ON event_purchase_reports (session_id);
CREATE INDEX IF NOT EXISTS ix_event_purchase_reports_event_id ON event_purchase_reports (event_id);
CREATE INDEX IF NOT EXISTS ix_event_purchase_reports_status ON event_purchase_reports (status);

CREATE TABLE IF NOT EXISTS event_login_failures (
	id SERIAL NOT NULL,
	key VARCHAR(80) NOT NULL,
	created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT (now() AT TIME ZONE 'utc'),
	PRIMARY KEY (id)
);
CREATE INDEX IF NOT EXISTS ix_event_login_failures_key ON event_login_failures (key);
CREATE INDEX IF NOT EXISTS ix_event_login_failures_created_at ON event_login_failures (created_at);

-- Ownership + RLS (deny-all for the Data API roles).
DO $$
DECLARE t TEXT;
BEGIN
  FOREACH t IN ARRAY ARRAY['events', 'event_zones', 'event_sessions', 'event_messages',
                           'event_selections', 'event_activity', 'event_purchase_reports',
                           'event_login_failures']
  LOOP
    EXECUTE format('ALTER TABLE %I ENABLE ROW LEVEL SECURITY', t);
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'sabi_backend') THEN
      EXECUTE format('ALTER TABLE %I OWNER TO sabi_backend', t);
    END IF;
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname IN ('anon', 'authenticated')) THEN
      EXECUTE format('DROP POLICY IF EXISTS deny_data_api ON %I', t);
      EXECUTE format('CREATE POLICY deny_data_api ON %I FOR ALL TO anon, authenticated '
                     'USING (false) WITH CHECK (false)', t);
    END IF;
  END LOOP;
END $$;
