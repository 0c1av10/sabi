-- Sabi initial schema (generated from backend/app/models.py).
-- The FastAPI backend connects as `sabi_backend`, which owns the tables (RLS stays
-- enabled with no policies, so the anon/authenticated Data API roles see nothing).
DO $$ BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'sabi_backend') THEN
    CREATE ROLE sabi_backend NOLOGIN;
  END IF;
END $$;
GRANT sabi_backend TO postgres;
GRANT USAGE, CREATE ON SCHEMA public TO sabi_backend;

CREATE TYPE orderstatus AS ENUM ('pending', 'approved', 'rejected', 'edited');

CREATE TABLE restaurants (
	id SERIAL NOT NULL, 
	name VARCHAR(200) NOT NULL, 
	slug VARCHAR(100) NOT NULL, 
	pin VARCHAR(20) NOT NULL, 
	owner_phone VARCHAR(30) NOT NULL, 
	welcome_message TEXT NOT NULL, 
	opening_hours TEXT NOT NULL, 
	currency VARCHAR(10) NOT NULL, 
	exchange_rate FLOAT NOT NULL, 
	eur_rate FLOAT NOT NULL, 
	bcv_auto BOOLEAN NOT NULL, 
	rates_date VARCHAR(10) NOT NULL, 
	rates_updated_at TIMESTAMP WITHOUT TIME ZONE, 
	email VARCHAR(200) NOT NULL, 
	website VARCHAR(300) NOT NULL, 
	tagline TEXT NOT NULL, 
	logo_url VARCHAR(500) NOT NULL, 
	brand_color VARCHAR(20) NOT NULL, 
	created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	PRIMARY KEY (id)
);

CREATE UNIQUE INDEX ix_restaurants_slug ON restaurants (slug);

ALTER TABLE restaurants ENABLE ROW LEVEL SECURITY;

CREATE TABLE customers (
	id SERIAL NOT NULL, 
	restaurant_id INTEGER NOT NULL, 
	phone VARCHAR(30) NOT NULL, 
	name VARCHAR(200) NOT NULL, 
	created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(restaurant_id) REFERENCES restaurants (id)
);

CREATE INDEX ix_customers_phone ON customers (phone);

CREATE INDEX ix_customers_restaurant_id ON customers (restaurant_id);

ALTER TABLE customers ENABLE ROW LEVEL SECURITY;

CREATE TABLE menu_items (
	id SERIAL NOT NULL, 
	restaurant_id INTEGER NOT NULL, 
	name VARCHAR(200) NOT NULL, 
	price FLOAT NOT NULL, 
	category VARCHAR(100) NOT NULL, 
	available BOOLEAN NOT NULL, 
	description TEXT NOT NULL, 
	image_url VARCHAR(500) NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(restaurant_id) REFERENCES restaurants (id)
);

CREATE INDEX ix_menu_items_restaurant_id ON menu_items (restaurant_id);

ALTER TABLE menu_items ENABLE ROW LEVEL SECURITY;

CREATE TABLE conversations (
	id SERIAL NOT NULL, 
	restaurant_id INTEGER NOT NULL, 
	customer_id INTEGER NOT NULL, 
	status VARCHAR(30) NOT NULL, 
	state_json TEXT NOT NULL, 
	created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	updated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(restaurant_id) REFERENCES restaurants (id), 
	FOREIGN KEY(customer_id) REFERENCES customers (id)
);

CREATE INDEX ix_conversations_customer_id ON conversations (customer_id);

CREATE INDEX ix_conversations_restaurant_id ON conversations (restaurant_id);

ALTER TABLE conversations ENABLE ROW LEVEL SECURITY;

CREATE TABLE messages (
	id SERIAL NOT NULL, 
	conversation_id INTEGER NOT NULL, 
	direction VARCHAR(10) NOT NULL, 
	body TEXT NOT NULL, 
	created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(conversation_id) REFERENCES conversations (id)
);

CREATE INDEX ix_messages_conversation_id ON messages (conversation_id);

ALTER TABLE messages ENABLE ROW LEVEL SECURITY;

CREATE TABLE orders (
	id SERIAL NOT NULL, 
	restaurant_id INTEGER NOT NULL, 
	conversation_id INTEGER NOT NULL, 
	customer_id INTEGER NOT NULL, 
	status orderstatus NOT NULL, 
	order_type VARCHAR(20) NOT NULL, 
	source VARCHAR(20) NOT NULL, 
	address VARCHAR(300) NOT NULL, 
	notes TEXT NOT NULL, 
	total FLOAT NOT NULL, 
	rejection_reason TEXT NOT NULL, 
	edit_summary TEXT NOT NULL, 
	created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	decided_at TIMESTAMP WITHOUT TIME ZONE, 
	PRIMARY KEY (id), 
	FOREIGN KEY(restaurant_id) REFERENCES restaurants (id), 
	FOREIGN KEY(conversation_id) REFERENCES conversations (id), 
	FOREIGN KEY(customer_id) REFERENCES customers (id)
);

CREATE INDEX ix_orders_conversation_id ON orders (conversation_id);

CREATE INDEX ix_orders_customer_id ON orders (customer_id);

CREATE INDEX ix_orders_restaurant_id ON orders (restaurant_id);

CREATE INDEX ix_orders_status ON orders (status);

ALTER TABLE orders ENABLE ROW LEVEL SECURITY;

CREATE TABLE order_items (
	id SERIAL NOT NULL, 
	order_id INTEGER NOT NULL, 
	menu_item_id INTEGER, 
	name VARCHAR(200) NOT NULL, 
	quantity INTEGER NOT NULL, 
	unit_price FLOAT NOT NULL, 
	extras TEXT NOT NULL, 
	notes TEXT NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(order_id) REFERENCES orders (id), 
	FOREIGN KEY(menu_item_id) REFERENCES menu_items (id)
);

CREATE INDEX ix_order_items_menu_item_id ON order_items (menu_item_id);

CREATE INDEX ix_order_items_order_id ON order_items (order_id);

ALTER TABLE order_items ENABLE ROW LEVEL SECURITY;

ALTER TYPE orderstatus OWNER TO sabi_backend;
ALTER TABLE restaurants OWNER TO sabi_backend;
ALTER TABLE menu_items OWNER TO sabi_backend;
ALTER TABLE customers OWNER TO sabi_backend;
ALTER TABLE conversations OWNER TO sabi_backend;
ALTER TABLE messages OWNER TO sabi_backend;
ALTER TABLE orders OWNER TO sabi_backend;
ALTER TABLE order_items OWNER TO sabi_backend;
