-- Cupcakes & Crumbs Co: PostgreSQL schema (matches queries in main.py)

CREATE TABLE IF NOT EXISTS products (
    id         SERIAL PRIMARY KEY,
    name       TEXT    NOT NULL,
    flavour    TEXT,
    pack_size  TEXT,
    price      INTEGER NOT NULL,          -- in rupees
    is_active  BOOLEAN NOT NULL DEFAULT TRUE
);

CREATE TABLE IF NOT EXISTS orders (
    id             SERIAL PRIMARY KEY,
    customer_name  TEXT NOT NULL,
    phone          VARCHAR(10) NOT NULL,
    address        TEXT NOT NULL,
    note           TEXT,
    status         TEXT NOT NULL DEFAULT 'pending',   -- pending | completed
    created_at     TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS order_items (
    id          SERIAL PRIMARY KEY,
    order_id    INTEGER NOT NULL REFERENCES orders(id) ON DELETE CASCADE,
    product_id  INTEGER NOT NULL REFERENCES products(id),
    quantity    INTEGER NOT NULL CHECK (quantity > 0),
    line_total  INTEGER NOT NULL
);

-- Example menu items
-- INSERT INTO products (name, flavour, pack_size, price) VALUES
--   ('Classic Cupcakes', 'Vanilla', 'Box of 6', 360),
--   ('Brownies', 'Double Chocolate', 'Box of 4', 300);
