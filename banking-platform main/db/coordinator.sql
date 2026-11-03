CREATE TABLE IF NOT EXISTS distributed_transfers (
    tx_id UUID PRIMARY KEY,
    request_id UUID NOT NULL UNIQUE,
    from_account TEXT NOT NULL,
    to_account TEXT NOT NULL,
    amount NUMERIC(20,2) NOT NULL CHECK (amount > 0),
    source_shard TEXT NOT NULL,
    target_shard TEXT NOT NULL,
    state TEXT NOT NULL CHECK (state IN (
        'INITIATED', 'PREPARING', 'PREPARED', 'COMMIT_DECIDED',
        'ABORT_DECIDED', 'COMPLETED')),
    decision TEXT CHECK (decision IN ('COMMIT', 'ABORT')),
    acknowledgements JSONB NOT NULL DEFAULT '{}'::jsonb,
    reason TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CHECK (source_shard <> target_shard)
);
CREATE INDEX IF NOT EXISTS idx_distributed_unfinished ON distributed_transfers(state)
    WHERE state <> 'COMPLETED';

