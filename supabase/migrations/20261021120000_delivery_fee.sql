-- Costo de delivery por restaurante (USD, como los precios del menú) y por pedido.
-- NULL en restaurants.delivery_fee = desconocido: el agente dice que el local lo confirma.
ALTER TABLE restaurants ADD COLUMN IF NOT EXISTS delivery_fee DOUBLE PRECISION;
ALTER TABLE restaurants ADD COLUMN IF NOT EXISTS delivery_info TEXT NOT NULL DEFAULT '';
ALTER TABLE orders ADD COLUMN IF NOT EXISTS delivery_fee DOUBLE PRECISION DEFAULT 0;

-- Delivery por zona: JSON [{"name": "Lechería", "fee": 2.0}] y la zona elegida en cada pedido.
ALTER TABLE restaurants ADD COLUMN IF NOT EXISTS delivery_zones TEXT NOT NULL DEFAULT '';
ALTER TABLE orders ADD COLUMN IF NOT EXISTS delivery_zone VARCHAR(100) NOT NULL DEFAULT '';
