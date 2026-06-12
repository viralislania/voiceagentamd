CREATE TABLE IF NOT EXISTS customers (
    customer_id   TEXT PRIMARY KEY,
    name          TEXT NOT NULL,
    phone         TEXT,
    kyc_verified  INTEGER DEFAULT 1
);

CREATE TABLE IF NOT EXISTS accounts (
    account_id     TEXT PRIMARY KEY,
    customer_id    TEXT REFERENCES customers(customer_id),
    account_type   TEXT,
    nickname       TEXT,
    account_number TEXT,
    balance        REAL DEFAULT 0,
    currency       TEXT DEFAULT 'INR',
    opened_on      TEXT
);

CREATE TABLE IF NOT EXISTS transactions (
    txn_id        TEXT PRIMARY KEY,
    account_id    TEXT REFERENCES accounts(account_id),
    amount        REAL,
    direction     TEXT,
    rail          TEXT,
    category      TEXT,
    status        TEXT,
    failure_code  TEXT,
    counterparty  TEXT,
    reference_no  TEXT,
    created_at    TEXT
);

CREATE TABLE IF NOT EXISTS deposit_products (
    product_id    TEXT PRIMARY KEY,
    kind          TEXT,
    name          TEXT,
    min_amount    REAL,
    max_amount    REAL,
    tenure_months INTEGER,
    interest_rate REAL
);

CREATE TABLE IF NOT EXISTS deposit_bookings (
    booking_id    TEXT PRIMARY KEY,
    customer_id   TEXT,
    product_id    TEXT,
    amount        REAL,
    tenure_months INTEGER,
    status        TEXT,
    created_at    TEXT
);

CREATE TABLE IF NOT EXISTS payees (
    payee_id       TEXT PRIMARY KEY,
    customer_id    TEXT,
    name           TEXT,
    account_number TEXT,
    ifsc           TEXT
);

CREATE TABLE IF NOT EXISTS payment_consents (
    consent_id    TEXT PRIMARY KEY,
    customer_id   TEXT,
    from_account  TEXT,
    payee_id      TEXT,
    amount        REAL,
    rail          TEXT,
    reason        TEXT,
    status        TEXT,
    otp           TEXT,
    created_at    TEXT
);

CREATE TABLE IF NOT EXISTS complaints (
    ticket_id     TEXT PRIMARY KEY,
    customer_id   TEXT,
    txn_id        TEXT,
    category      TEXT,
    description   TEXT,
    topics        TEXT,
    sentiment     TEXT,
    status        TEXT DEFAULT 'open',
    created_at    TEXT
);
