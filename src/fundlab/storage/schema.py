SCHEMA_VERSION = 1

SCHEMA_SQL = """
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS schema_version (
    version INTEGER PRIMARY KEY,
    applied_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS funds (
    fund_id TEXT PRIMARY KEY,
    fund_code TEXT NOT NULL,
    share_class TEXT NOT NULL,
    fund_name TEXT NOT NULL,
    fund_type TEXT NOT NULL,
    benchmark_code TEXT,
    manager_name TEXT,
    inception_date TEXT,
    management_fee REAL,
    custodian_fee REAL,
    source TEXT NOT NULL,
    fetched_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS fund_nav (
    fund_id TEXT NOT NULL,
    nav_date TEXT NOT NULL,
    unit_nav REAL NOT NULL,
    accumulated_nav REAL,
    adjusted_nav REAL,
    source TEXT NOT NULL,
    fetched_at TEXT NOT NULL,
    quality_status TEXT NOT NULL,
    PRIMARY KEY (fund_id, nav_date, source)
);

CREATE INDEX IF NOT EXISTS idx_fund_nav_lookup ON fund_nav(fund_id, nav_date);

CREATE TABLE IF NOT EXISTS transactions (
    transaction_id TEXT PRIMARY KEY,
    external_id TEXT,
    account TEXT NOT NULL,
    fund_code TEXT NOT NULL,
    share_class TEXT NOT NULL,
    trade_date TEXT NOT NULL,
    action TEXT NOT NULL,
    amount REAL NOT NULL,
    shares REAL NOT NULL,
    nav REAL,
    fee REAL NOT NULL,
    dividend REAL NOT NULL,
    source TEXT NOT NULL,
    payload_hash TEXT NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS documents (
    document_id TEXT PRIMARY KEY,
    document_type TEXT NOT NULL,
    subject_ids_json TEXT NOT NULL,
    source_name TEXT NOT NULL,
    source_url TEXT,
    published_at TEXT NOT NULL,
    effective_at TEXT,
    fetched_at TEXT NOT NULL,
    content_hash TEXT NOT NULL UNIQUE,
    normalized_text TEXT NOT NULL,
    trust_level TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS evidence_items (
    evidence_id TEXT PRIMARY KEY,
    document_id TEXT NOT NULL,
    subject_id TEXT NOT NULL,
    quote TEXT NOT NULL,
    published_at TEXT NOT NULL,
    source_name TEXT NOT NULL,
    source_url TEXT,
    trust_level TEXT NOT NULL,
    FOREIGN KEY (document_id) REFERENCES documents(document_id)
);

CREATE TABLE IF NOT EXISTS ai_runs (
    run_id TEXT PRIMARY KEY,
    subject_id TEXT NOT NULL,
    provider TEXT NOT NULL,
    model TEXT NOT NULL,
    prompt_name TEXT NOT NULL,
    prompt_version TEXT NOT NULL,
    input_hash TEXT NOT NULL,
    output_schema_version TEXT NOT NULL,
    started_at TEXT NOT NULL,
    finished_at TEXT,
    latency_ms INTEGER,
    prompt_tokens INTEGER NOT NULL DEFAULT 0,
    completion_tokens INTEGER NOT NULL DEFAULT 0,
    estimated_cost_usd REAL NOT NULL DEFAULT 0,
    cached INTEGER NOT NULL DEFAULT 0,
    success INTEGER NOT NULL,
    output_json TEXT,
    error TEXT
);

CREATE INDEX IF NOT EXISTS idx_ai_runs_input ON ai_runs(input_hash, prompt_version, model);

CREATE TABLE IF NOT EXISTS data_quality_events (
    event_id TEXT PRIMARY KEY,
    subject_id TEXT,
    provider TEXT,
    event_type TEXT NOT NULL,
    severity TEXT NOT NULL,
    message TEXT NOT NULL,
    details_json TEXT,
    created_at TEXT NOT NULL,
    resolved_at TEXT
);

CREATE TABLE IF NOT EXISTS analysis_reports (
    report_id TEXT PRIMARY KEY,
    fund_id TEXT NOT NULL,
    generated_at TEXT NOT NULL,
    report_json TEXT NOT NULL
);
"""
