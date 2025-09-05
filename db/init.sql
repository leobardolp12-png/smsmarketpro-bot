-- init.sql : crea tablas básicas
CREATE TABLE IF NOT EXISTS clients (
    id SERIAL PRIMARY KEY,
    user_id BIGINT UNIQUE NOT NULL,
    name TEXT,
    balance NUMERIC DEFAULT 0,
    orders_count INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT now()
);

CREATE TABLE IF NOT EXISTS operators (
    id SERIAL PRIMARY KEY,
    user_id BIGINT UNIQUE NOT NULL,
    name TEXT,
    balance_retirable NUMERIC DEFAULT 0,
    accepted INTEGER DEFAULT 0,
    completed INTEGER DEFAULT 0,
    cancelled INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT now()
);

CREATE TABLE IF NOT EXISTS orders (
    id SERIAL PRIMARY KEY,
    order_code TEXT UNIQUE,
    client_id INTEGER REFERENCES clients(id),
    app TEXT,
    quantity INTEGER,
    price_unit NUMERIC,
    total NUMERIC,
    status TEXT,
    operator_id INTEGER REFERENCES operators(id),
    created_at TIMESTAMP DEFAULT now(),
    updated_at TIMESTAMP DEFAULT now()
);

CREATE TABLE IF NOT EXISTS numbers (
    id SERIAL PRIMARY KEY,
    order_id INTEGER REFERENCES orders(id),
    number TEXT,
    app TEXT,
    operator_id INTEGER,
    status TEXT,
    created_at TIMESTAMP DEFAULT now()
);

CREATE TABLE IF NOT EXISTS recargas (
    id SERIAL PRIMARY KEY,
    client_id INTEGER REFERENCES clients(id),
    amount NUMERIC,
    status TEXT,
    operation_code TEXT,
    receipt_path TEXT,
    created_at TIMESTAMP DEFAULT now()
);
