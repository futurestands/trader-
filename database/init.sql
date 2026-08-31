-- PostgreSQL schema for AETMS
-- Enables pgcrypto for gen_random_uuid()
CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- Append-only trade ledger for auditability
CREATE TABLE IF NOT EXISTS trade_ledger (
    id BIGSERIAL PRIMARY KEY,
    trace_id UUID NOT NULL DEFAULT gen_random_uuid(),
    symbol TEXT NOT NULL,
    side TEXT NOT NULL,
    lots NUMERIC(18,6) NOT NULL,
    entry_price NUMERIC(18,8) NOT NULL,
    exit_price NUMERIC(18,8),
    realized_pnl NUMERIC(18,8) DEFAULT 0,
    opened_at TIMESTAMPTZ DEFAULT now(),
    closed_at TIMESTAMPTZ,
    status TEXT NOT NULL DEFAULT 'open',
    raw_order JSONB,
    CONSTRAINT trade_ledger_trace_id_unique UNIQUE (trace_id)
);

CREATE INDEX IF NOT EXISTS idx_trade_ledger_symbol ON trade_ledger(symbol);
CREATE INDEX IF NOT EXISTS idx_trade_ledger_status ON trade_ledger(status);

-- System events for audit and diagnostics
CREATE TABLE IF NOT EXISTS system_events (
    id BIGSERIAL PRIMARY KEY,
    trace_id UUID NOT NULL DEFAULT gen_random_uuid(),
    event_type TEXT NOT NULL,
    payload JSONB,
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_system_events_type ON system_events(event_type);

-- Lightweight system health table used for daily start-of-day balances and metrics
CREATE TABLE IF NOT EXISTS system_health (
    id BIGSERIAL PRIMARY KEY,
    date DATE NOT NULL,
    starting_balance NUMERIC(18,8) NOT NULL,
    equity NUMERIC(18,8),
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE UNIQUE INDEX IF NOT EXISTS ux_system_health_date ON system_health(date);
