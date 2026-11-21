-- Datacheck Quality Monitor — SQLite schema.
-- Applied idempotently on every boot by datacheck.db.init_db().

PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS users (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    email         TEXT    NOT NULL UNIQUE,
    password_hash TEXT    NOT NULL,
    display_name  TEXT    NOT NULL,
    role          TEXT    NOT NULL DEFAULT 'engineer' CHECK (role IN ('engineer', 'lead')),
    created_at    TEXT    NOT NULL
);

CREATE TABLE IF NOT EXISTS sessions (
    id         TEXT    PRIMARY KEY,
    user_id    INTEGER NOT NULL REFERENCES users (id) ON DELETE CASCADE,
    created_at TEXT    NOT NULL,
    expires_at TEXT    NOT NULL
);

CREATE INDEX IF NOT EXISTS ix_sessions_user ON sessions (user_id);

CREATE TABLE IF NOT EXISTS datasets (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    slug           TEXT    NOT NULL UNIQUE,
    name           TEXT    NOT NULL,
    description    TEXT,
    row_count      INTEGER NOT NULL,
    generator_seed INTEGER NOT NULL,
    created_at     TEXT    NOT NULL
);

CREATE TABLE IF NOT EXISTS source_rows (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    dataset_id   INTEGER NOT NULL REFERENCES datasets (id) ON DELETE CASCADE,
    row_index    INTEGER NOT NULL,
    payload_json TEXT    NOT NULL,
    UNIQUE (dataset_id, row_index)
);

CREATE INDEX IF NOT EXISTS ix_source_rows_dataset ON source_rows (dataset_id);

CREATE TABLE IF NOT EXISTS rules (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    dataset_id  INTEGER NOT NULL REFERENCES datasets (id) ON DELETE CASCADE,
    name        TEXT    NOT NULL,
    kind        TEXT    NOT NULL CHECK (kind IN ('null', 'range', 'unique')),
    column_name TEXT    NOT NULL,
    params_json TEXT    NOT NULL DEFAULT '{}',
    enabled     INTEGER NOT NULL DEFAULT 1 CHECK (enabled IN (0, 1)),
    created_at  TEXT    NOT NULL,
    UNIQUE (dataset_id, name)
);

CREATE INDEX IF NOT EXISTS ix_rules_dataset ON rules (dataset_id);

CREATE TABLE IF NOT EXISTS validation_runs (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    dataset_id    INTEGER NOT NULL REFERENCES datasets (id) ON DELETE CASCADE,
    run_number    INTEGER NOT NULL,
    started_at    TEXT    NOT NULL,
    finished_at   TEXT    NOT NULL,
    "trigger"     TEXT    NOT NULL CHECK ("trigger" IN ('seed', 'manual')),
    checked_rows  INTEGER NOT NULL,
    total_rules   INTEGER NOT NULL,
    failed_rules  INTEGER NOT NULL,
    quality_score REAL    NOT NULL,
    UNIQUE (dataset_id, run_number)
);

CREATE INDEX IF NOT EXISTS ix_runs_dataset ON validation_runs (dataset_id, run_number);

CREATE TABLE IF NOT EXISTS rule_results (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id        INTEGER NOT NULL REFERENCES validation_runs (id) ON DELETE CASCADE,
    rule_id       INTEGER NOT NULL REFERENCES rules (id) ON DELETE CASCADE,
    passed        INTEGER NOT NULL CHECK (passed IN (0, 1)),
    checked_count INTEGER NOT NULL,
    failing_count INTEGER NOT NULL,
    UNIQUE (run_id, rule_id)
);

CREATE INDEX IF NOT EXISTS ix_rule_results_run ON rule_results (run_id);
CREATE INDEX IF NOT EXISTS ix_rule_results_rule ON rule_results (rule_id);

CREATE TABLE IF NOT EXISTS failing_rows (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id      INTEGER NOT NULL REFERENCES validation_runs (id) ON DELETE CASCADE,
    rule_id     INTEGER NOT NULL REFERENCES rules (id) ON DELETE CASCADE,
    row_index   INTEGER NOT NULL,
    column_name TEXT    NOT NULL,
    value_text  TEXT,
    reason      TEXT    NOT NULL
);

CREATE INDEX IF NOT EXISTS ix_failing_rows_run_rule ON failing_rows (run_id, rule_id);

-- Sign-in throttle counters (single process, SQLite-backed, windowed).
CREATE TABLE IF NOT EXISTS rate_limit (
    key          TEXT    NOT NULL,
    window_start INTEGER NOT NULL,
    count        INTEGER NOT NULL,
    PRIMARY KEY (key, window_start)
);
