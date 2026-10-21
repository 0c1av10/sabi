-- Costo de delivery por restaurante (USD, como los precios del menú) y por pedido.
-- NULL en restaurants.delivery_fee = desconocido: el agente dice que el local lo confirma.
ALTER TABLE restaurants ADD COLUMN IF NOT EXISTS delivery_fee DOUBLE PRECISION;
ALTER TABLE restaurants ADD COLUMN IF NOT EXISTS delivery_info TEXT NOT NULL DEFAULT '';
ALTER TABLE orders ADD COLUMN IF NOT EXISTS delivery_fee DOUBLE PRECISION DEFAULT 0;
