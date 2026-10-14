-- WhatsApp message id (wamid) for inbound deduplication of webhook retries.
ALTER TABLE messages ADD COLUMN IF NOT EXISTS external_id VARCHAR(200);
CREATE INDEX IF NOT EXISTS ix_messages_external_id ON messages (external_id);

ALTER TABLE orders ADD COLUMN IF NOT EXISTS payment_status VARCHAR(20) NOT NULL DEFAULT 'pending';
ALTER TABLE orders ADD COLUMN IF NOT EXISTS payment_method VARCHAR(40) NOT NULL DEFAULT '';
ALTER TABLE orders ADD COLUMN IF NOT EXISTS payment_reference VARCHAR(160) NOT NULL DEFAULT '';
CREATE INDEX IF NOT EXISTS ix_orders_payment_status ON orders (payment_status);
