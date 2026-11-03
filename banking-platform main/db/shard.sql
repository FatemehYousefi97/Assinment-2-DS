CREATE TABLE IF NOT EXISTS accounts (
    account_id TEXT PRIMARY KEY CHECK (account_id ~ '^A[0-9]{4}$'),
    balance NUMERIC(20,2) NOT NULL CHECK (balance >= 0)
);
CREATE TABLE IF NOT EXISTS operation_receipts (
    request_id UUID PRIMARY KEY,
    request_hash TEXT NOT NULL,
    result JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS transfer_receipts (
    tx_id UUID PRIMARY KEY,
    role TEXT NOT NULL CHECK (role IN ('DEBIT', 'CREDIT')),
    account_id TEXT NOT NULL REFERENCES accounts(account_id),
    amount NUMERIC(20,2) NOT NULL CHECK (amount > 0),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS participant_journal (
    tx_id UUID PRIMARY KEY,
    gid TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('PREPARED', 'ABORTING', 'ABORTED', 'COMMITTED')),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

