-- WhatsApp message id (wamid) for inbound deduplication of webhook retries.
ALTER TABLE messages ADD COLUMN IF NOT EXISTS external_id VARCHAR(200);
CREATE INDEX IF NOT EXISTS ix_messages_external_id ON messages (external_id);
