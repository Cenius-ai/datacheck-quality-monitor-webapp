"""Validation engine: checks, run persistence and sample caps."""

from __future__ import annotations

import json

from datacheck import repositories as repo
from datacheck.engine.checks import (
    check_null,
    check_range,
    check_uniqueness,
    evaluate_rule,
)
from datacheck.engine.validator import compute_quality_score, run_validation


def _rule(kind: str, column: str, params: dict | None = None) -> dict:
    return {"kind": kind, "column_name": column, "params": params or {}}


# --------------------------------------------------------------------- checks
def test_null_check_flags_missing_and_blank_values():
    rows = [{"email": "a@b.co"}, {"email": None}, {"email": ""}, {"email": "c@d.co"}]
    outcome = check_null(rows, "email")
    assert outcome.checked_count == 4
    assert [failure["row_index"] for failure in outcome.failures] == [1, 2]
    assert outcome.failures[0]["value_text"] is None
    assert "missing" in outcome.failures[0]["reason"]


def test_range_check_reports_bounds_and_skips_nulls():
    rows = [{"amount": 10}, {"amount": None}, {"amount": 500}, {"amount": -5}, {"amount": "n/a"}]
    outcome = check_range(rows, "amount", minimum=0, maximum=100)
    assert outcome.checked_count == 5
    reasons = [failure["reason"] for failure in outcome.failures]
    assert len(reasons) == 3
    assert "above the maximum" in reasons[0]
    assert "below the minimum" in reasons[1]
    assert "not numeric" in reasons[2]


def test_uniqueness_counts_every_duplicated_row():
    rows = [{"id": "a"}, {"id": "b"}, {"id": "a"}, {"id": "a"}, {"id": None}, {"id": "c"}]
    outcome = check_uniqueness(rows, "id")
    assert outcome.checked_count == 6
    assert outcome.failing_count == 3
    assert all("3 rows share this value" in failure["reason"] for failure in outcome.failures)


def test_evaluate_rule_dispatches_kinds():
    rows = [{"n": 1}, {"n": 1}, {"n": None}]
    assert evaluate_rule(_rule("null", "n"), rows).failing_count == 1
    assert evaluate_rule(_rule("unique", "n"), rows).failing_count == 2
    assert evaluate_rule(_rule("range", "n", {"min": 0, "max": 5}), rows).failing_count == 0


def test_quality_score_is_the_share_of_passing_checks():
    assert compute_quality_score(0, 0) == 100.0
    assert compute_quality_score(500, 0) == 100.0
    assert compute_quality_score(500, 5) == 99.0
    assert compute_quality_score(1000, 250) == 75.0


# ------------------------------------------------------------------ run writes
def _scratch_dataset(slug: str, rows: list[dict], rules: list[dict]) -> int:
    dataset_id = repo.create_dataset(slug, slug.title(), "scratch", len(rows), 1)
    repo.replace_source_rows(dataset_id, rows)
    for rule in rules:
        repo.create_rule(dataset_id, rule["name"], rule["kind"], rule["column"], rule.get("params", {}))
    return dataset_id


def test_manual_run_writes_run_results_and_capped_samples():
    rows = [{"value": None if index < 30 else index} for index in range(100)]
    dataset_id = _scratch_dataset(
        "scratch_nulls",
        rows,
        [{"name": "value is present", "kind": "null", "column": "value"}],
    )
    run = run_validation(dataset_id, trigger="manual")

    assert run["checked_rows"] == 100
    assert run["total_rules"] == 1
    assert run["failed_rules"] == 1
    assert run["quality_score"] == 70.0

    results = repo.results_for_run(run["id"])
    assert len(results) == 1
    assert results[0]["passed"] == 0
    assert results[0]["checked_count"] == 100
    assert results[0]["failing_count"] == 30

    samples = repo.failures_for_run(run["id"], results[0]["rule_id"], limit=100)
    assert len(samples) == 20, "failing row samples are capped at 20"
    assert samples[0]["row_index"] == 0
    assert samples[0]["column_name"] == "value"
    assert samples[0]["value_text"] is None
    assert samples[0]["reason"]


def test_duplicate_rule_results_are_rejected_by_the_unique_constraint():
    import pytest
    from sqlalchemy.exc import IntegrityError

    from datacheck.db import connect

    run = repo.latest_run(repo.get_dataset_by_slug("orders_ledger")["id"])
    existing = repo.results_for_run(run["id"])[0]
    with pytest.raises(IntegrityError):
        with connect() as conn:
            conn.execute(
                """
                INSERT INTO rule_results (run_id, rule_id, passed, checked_count, failing_count)
                VALUES (:run_id, :rule_id, 0, 1, 1)
                """,
                {"run_id": run["id"], "rule_id": existing["rule_id"]},
            )


def test_run_validation_reports_unknown_dataset():
    import pytest

    from datacheck.engine.validator import DatasetNotFound

    with pytest.raises(DatasetNotFound):
        run_validation(999_999)


def test_disabled_rules_are_not_evaluated():
    rows = [{"n": None}, {"n": 1}]
    dataset_id = _scratch_dataset(
        "scratch_disabled",
        rows,
        [{"name": "n present", "kind": "null", "column": "n"}],
    )
    rule = repo.list_rules(dataset_id)[0]
    repo.set_rule_enabled(rule["id"], False)
    run = run_validation(dataset_id)
    assert run["total_rules"] == 0
    assert run["quality_score"] == 100.0
    assert repo.results_for_run(run["id"]) == []


def test_failing_sample_payload_is_json_serialisable():
    run = repo.latest_run(repo.get_dataset_by_slug("billing_transactions")["id"])
    results = repo.results_for_run(run["id"])
    failures = repo.failures_for_run(run["id"], results[0]["rule_id"])
    assert failures
    payload = json.dumps(failures)
    assert "reason" in payload
