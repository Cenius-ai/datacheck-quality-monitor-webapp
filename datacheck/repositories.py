"""Thin repository layer over SQLAlchemy Core.

No ORM entities: the dashboard reads whole rows and the validation engine writes
bulk results, so explicit SQL keeps both paths fast and greppable. Every query
uses bound parameters.
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from datetime import UTC, datetime, timedelta
from typing import Any

from .db import connect, fetch_all, fetch_one

ISO_FORMAT = "%Y-%m-%dT%H:%M:%SZ"


def utc_now() -> str:
    return datetime.now(UTC).strftime(ISO_FORMAT)


def to_iso(moment: datetime) -> str:
    return moment.astimezone(UTC).strftime(ISO_FORMAT)


def parse_iso(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


# --------------------------------------------------------------------------
# users
# --------------------------------------------------------------------------
def get_user_by_email(email: str) -> dict | None:
    return fetch_one("SELECT * FROM users WHERE email = :email", {"email": email.strip().lower()})


def get_user(user_id: int) -> dict | None:
    return fetch_one("SELECT * FROM users WHERE id = :id", {"id": user_id})


def create_user(
    email: str,
    password_hash: str,
    display_name: str,
    role: str = "engineer",
    created_at: str | None = None,
) -> int:
    """`created_at` is passed by the seeder so a fresh install is reproducible."""
    with connect() as conn:
        result = conn.execute(
            """
            INSERT INTO users (email, password_hash, display_name, role, created_at)
            VALUES (:email, :password_hash, :display_name, :role, :created_at)
            """,
            {
                "email": email.strip().lower(),
                "password_hash": password_hash,
                "display_name": display_name,
                "role": role,
                "created_at": created_at or utc_now(),
            },
        )
        return int(result.lastrowid)


def count_users() -> int:
    row = fetch_one("SELECT COUNT(*) AS n FROM users")
    return int(row["n"]) if row else 0


# --------------------------------------------------------------------------
# sessions
# --------------------------------------------------------------------------
def create_session(token: str, user_id: int, ttl_days: int) -> str:
    created = datetime.now(UTC)
    expires = created + timedelta(days=ttl_days)
    with connect() as conn:
        conn.execute(
            """
            INSERT INTO sessions (id, user_id, created_at, expires_at)
            VALUES (:id, :user_id, :created_at, :expires_at)
            """,
            {
                "id": token,
                "user_id": user_id,
                "created_at": to_iso(created),
                "expires_at": to_iso(expires),
            },
        )
    return to_iso(expires)


def get_session(token: str) -> dict | None:
    if not token:
        return None
    return fetch_one(
        """
        SELECT s.id AS session_id, s.expires_at, u.id AS user_id, u.email,
               u.display_name, u.role
        FROM sessions s
        JOIN users u ON u.id = s.user_id
        WHERE s.id = :token
        """,
        {"token": token},
    )


def delete_session(token: str) -> None:
    with connect() as conn:
        conn.execute("DELETE FROM sessions WHERE id = :token", {"token": token})


# --------------------------------------------------------------------------
# datasets
# --------------------------------------------------------------------------
def list_datasets() -> list[dict]:
    return fetch_all(
        """
        SELECT d.*, (SELECT COUNT(*) FROM rules r WHERE r.dataset_id = d.id) AS rule_count
        FROM datasets d
        ORDER BY d.id
        """
    )


def get_dataset(dataset_id: int) -> dict | None:
    return fetch_one("SELECT * FROM datasets WHERE id = :id", {"id": dataset_id})


def get_dataset_by_slug(slug: str) -> dict | None:
    return fetch_one("SELECT * FROM datasets WHERE slug = :slug", {"slug": slug})


def create_dataset(
    slug: str,
    name: str,
    description: str,
    row_count: int,
    generator_seed: int,
    created_at: str | None = None,
) -> int:
    with connect() as conn:
        result = conn.execute(
            """
            INSERT INTO datasets (slug, name, description, row_count, generator_seed, created_at)
            VALUES (:slug, :name, :description, :row_count, :generator_seed, :created_at)
            """,
            {
                "slug": slug,
                "name": name,
                "description": description,
                "row_count": row_count,
                "generator_seed": generator_seed,
                "created_at": created_at or utc_now(),
            },
        )
        return int(result.lastrowid)


# --------------------------------------------------------------------------
# source rows
# --------------------------------------------------------------------------
def replace_source_rows(dataset_id: int, rows: Sequence[dict]) -> None:
    with connect() as conn:
        conn.execute("DELETE FROM source_rows WHERE dataset_id = :id", {"id": dataset_id})
        conn.execute(
            """
            INSERT INTO source_rows (dataset_id, row_index, payload_json)
            VALUES (:dataset_id, :row_index, :payload_json)
            """,
            [
                {
                    "dataset_id": dataset_id,
                    "row_index": index,
                    "payload_json": json.dumps(row, sort_keys=True),
                }
                for index, row in enumerate(rows)
            ],
        )


def load_source_rows(dataset_id: int) -> list[dict]:
    rows = fetch_all(
        "SELECT row_index, payload_json FROM source_rows WHERE dataset_id = :id ORDER BY row_index",
        {"id": dataset_id},
    )
    return [json.loads(row["payload_json"]) for row in rows]


def dataset_columns(dataset_id: int) -> list[str]:
    row = fetch_one(
        "SELECT payload_json FROM source_rows WHERE dataset_id = :id ORDER BY row_index LIMIT 1",
        {"id": dataset_id},
    )
    if not row:
        return []
    return sorted(json.loads(row["payload_json"]).keys())


def count_source_rows(dataset_id: int) -> int:
    row = fetch_one(
        "SELECT COUNT(*) AS n FROM source_rows WHERE dataset_id = :id", {"id": dataset_id}
    )
    return int(row["n"]) if row else 0


# --------------------------------------------------------------------------
# rules
# --------------------------------------------------------------------------
def list_rules(dataset_id: int) -> list[dict]:
    rules = fetch_all(
        "SELECT * FROM rules WHERE dataset_id = :id ORDER BY id", {"id": dataset_id}
    )
    for rule in rules:
        rule["params"] = json.loads(rule["params_json"] or "{}")
        rule["enabled"] = bool(rule["enabled"])
    return rules


def list_enabled_rules(dataset_id: int) -> list[dict]:
    return [rule for rule in list_rules(dataset_id) if rule["enabled"]]


def get_rule(rule_id: int) -> dict | None:
    rule = fetch_one("SELECT * FROM rules WHERE id = :id", {"id": rule_id})
    if rule:
        rule["params"] = json.loads(rule["params_json"] or "{}")
        rule["enabled"] = bool(rule["enabled"])
    return rule


def create_rule(
    dataset_id: int,
    name: str,
    kind: str,
    column_name: str,
    params: dict[str, Any],
    created_at: str | None = None,
) -> int:
    with connect() as conn:
        result = conn.execute(
            """
            INSERT INTO rules (dataset_id, name, kind, column_name, params_json, enabled, created_at)
            VALUES (:dataset_id, :name, :kind, :column_name, :params_json, 1, :created_at)
            """,
            {
                "dataset_id": dataset_id,
                "name": name,
                "kind": kind,
                "column_name": column_name,
                "params_json": json.dumps(params, sort_keys=True),
                "created_at": created_at or utc_now(),
            },
        )
        return int(result.lastrowid)


def set_rule_enabled(rule_id: int, enabled: bool) -> None:
    with connect() as conn:
        conn.execute(
            "UPDATE rules SET enabled = :enabled WHERE id = :id",
            {"enabled": 1 if enabled else 0, "id": rule_id},
        )


# --------------------------------------------------------------------------
# validation runs
# --------------------------------------------------------------------------
def next_run_number(dataset_id: int) -> int:
    row = fetch_one(
        "SELECT COALESCE(MAX(run_number), 0) AS n FROM validation_runs WHERE dataset_id = :id",
        {"id": dataset_id},
    )
    return int(row["n"]) + 1 if row else 1


def insert_run(
    dataset_id: int,
    run_number: int,
    started_at: str,
    finished_at: str,
    trigger: str,
    checked_rows: int,
    total_rules: int,
    failed_rules: int,
    quality_score: float,
) -> int:
    with connect() as conn:
        result = conn.execute(
            """
            INSERT INTO validation_runs
                (dataset_id, run_number, started_at, finished_at, "trigger",
                 checked_rows, total_rules, failed_rules, quality_score)
            VALUES
                (:dataset_id, :run_number, :started_at, :finished_at, :trigger,
                 :checked_rows, :total_rules, :failed_rules, :quality_score)
            """,
            {
                "dataset_id": dataset_id,
                "run_number": run_number,
                "started_at": started_at,
                "finished_at": finished_at,
                "trigger": trigger,
                "checked_rows": checked_rows,
                "total_rules": total_rules,
                "failed_rules": failed_rules,
                "quality_score": quality_score,
            },
        )
        return int(result.lastrowid)


def get_run(run_id: int) -> dict | None:
    return fetch_one(
        """
        SELECT r.*, d.name AS dataset_name, d.slug AS dataset_slug
        FROM validation_runs r
        JOIN datasets d ON d.id = r.dataset_id
        WHERE r.id = :id
        """,
        {"id": run_id},
    )


def list_runs(dataset_id: int, limit: int = 21) -> list[dict]:
    rows = fetch_all(
        """
        SELECT * FROM validation_runs
        WHERE dataset_id = :id
        ORDER BY run_number DESC
        LIMIT :limit
        """,
        {"id": dataset_id, "limit": limit},
    )
    return rows


def latest_run(dataset_id: int) -> dict | None:
    rows = list_runs(dataset_id, limit=1)
    return rows[0] if rows else None


def count_runs(dataset_id: int) -> int:
    row = fetch_one(
        "SELECT COUNT(*) AS n FROM validation_runs WHERE dataset_id = :id", {"id": dataset_id}
    )
    return int(row["n"]) if row else 0


# --------------------------------------------------------------------------
# rule results
# --------------------------------------------------------------------------
def results_for_run(run_id: int) -> list[dict]:
    return fetch_all(
        """
        SELECT rr.*, r.name AS rule_name, r.kind, r.column_name, r.enabled, r.dataset_id
        FROM rule_results rr
        JOIN rules r ON r.id = rr.rule_id
        WHERE rr.run_id = :run_id
        ORDER BY r.id
        """,
        {"run_id": run_id},
    )


def rule_history(rule_id: int, limit: int = 21) -> list[dict]:
    rows = fetch_all(
        """
        SELECT rr.*, v.run_number, v.started_at, v.quality_score
        FROM rule_results rr
        JOIN validation_runs v ON v.id = rr.run_id
        WHERE rr.rule_id = :rule_id
        ORDER BY v.run_number DESC
        LIMIT :limit
        """,
        {"rule_id": rule_id, "limit": limit},
    )
    return list(reversed(rows))


# --------------------------------------------------------------------------
# failing rows
# --------------------------------------------------------------------------
def failures_for_run(run_id: int, rule_id: int | None = None, limit: int = 20) -> list[dict]:
    sql = """
        SELECT f.*, r.name AS rule_name
        FROM failing_rows f
        JOIN rules r ON r.id = f.rule_id
        WHERE f.run_id = :run_id
    """
    params: dict[str, Any] = {"run_id": run_id, "limit": limit}
    if rule_id is not None:
        sql += " AND f.rule_id = :rule_id"
        params["rule_id"] = rule_id
    sql += " ORDER BY f.rule_id, f.row_index LIMIT :limit"
    return fetch_all(sql, params)


def failure_sample_counts(run_id: int) -> dict[int, int]:
    rows = fetch_all(
        "SELECT rule_id, COUNT(*) AS n FROM failing_rows WHERE run_id = :run_id GROUP BY rule_id",
        {"run_id": run_id},
    )
    return {int(row["rule_id"]): int(row["n"]) for row in rows}


# --------------------------------------------------------------------------
# rate limiting (single process, windowed, SQLite-backed)
# --------------------------------------------------------------------------
def bump_rate_limit(key: str, window_start: int) -> int:
    with connect() as conn:
        conn.execute(
            """
            INSERT INTO rate_limit (key, window_start, count) VALUES (:key, :window_start, 1)
            ON CONFLICT (key, window_start) DO UPDATE SET count = count + 1
            """,
            {"key": key, "window_start": window_start},
        )
        row = conn.execute(
            "SELECT count FROM rate_limit WHERE key = :key AND window_start = :window_start",
            {"key": key, "window_start": window_start},
        ).fetchone()
        return int(row[0]) if row else 0


def clear_rate_limit(key: str) -> None:
    with connect() as conn:
        conn.execute("DELETE FROM rate_limit WHERE key = :key", {"key": key})
