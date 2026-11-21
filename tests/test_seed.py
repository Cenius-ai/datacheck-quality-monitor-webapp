"""Seed data: determinism, coverage and the regression the demo relies on."""

from __future__ import annotations

import json
from datetime import UTC, date, datetime, time, timedelta

from datacheck import repositories as repo
from datacheck.config import HISTORY_RUNS, ROWS_PER_DATASET, seed_epoch_date
from datacheck.seed.datasets import DATASET_SPECS, SPECS_BY_SLUG
from datacheck.seed.generator import build_rows

ANCHOR = datetime.combine(date(2026, 3, 1), time(2, 15), tzinfo=UTC)


def seeded_datasets() -> list[dict]:
    """Only the three spec'd demo datasets (tests may add scratch datasets)."""
    return [row for row in repo.list_datasets() if row["slug"] in SPECS_BY_SLUG]


def test_seeded_datasets_have_rows_and_rules():
    datasets = seeded_datasets()
    assert len(datasets) == 3
    for dataset in datasets:
        assert repo.count_source_rows(dataset["id"]) == ROWS_PER_DATASET
        rules = repo.list_rules(dataset["id"])
        assert len(rules) >= 4
        assert {"null", "range", "unique"} <= {rule["kind"] for rule in rules}


def seeded_runs(dataset_id: int) -> list[dict]:
    runs = repo.list_runs(dataset_id, limit=200)
    return [run for run in runs if run["trigger"] == "seed"]


def test_every_dataset_has_a_full_run_history():
    total_pairs = 0
    for dataset in seeded_datasets():
        runs = seeded_runs(dataset["id"])
        assert len(runs) == HISTORY_RUNS
        known_rules = {rule["id"] for rule in repo.list_rules(dataset["id"])}
        for run in runs:
            results = repo.results_for_run(run["id"])
            rule_ids = [row["rule_id"] for row in results]
            assert len(rule_ids) == run["total_rules"] == 5, "one result per evaluated rule"
            assert len(set(rule_ids)) == len(rule_ids)
            assert set(rule_ids) <= known_rules
            for row in results:
                assert row["checked_count"] == ROWS_PER_DATASET
            total_pairs += len(rule_ids)
    assert total_pairs == 63 * 5, "every run x rule pair has exactly one result"


def test_regression_dataset_drops_and_the_others_stay_stable():
    by_slug = {row["slug"]: row for row in seeded_datasets()}
    scores = {}
    for slug, dataset in by_slug.items():
        runs = list(reversed(seeded_runs(dataset["id"])))
        scores[slug] = [run["quality_score"] for run in runs]

    regression = scores["billing_transactions"]
    earlier_mean = sum(regression[:-3]) / len(regression[:-3])
    recent_mean = sum(regression[-3:]) / 3
    assert earlier_mean - recent_mean >= 15, "the demo needs a visible regression"

    for slug in ("orders_ledger", "signup_cohort"):
        assert max(scores[slug]) - min(scores[slug]) <= 5, f"{slug} must stay in a tight band"


def test_latest_seeded_run_has_failing_samples():
    for dataset in seeded_datasets():
        latest = seeded_runs(dataset["id"])[0]
        failing = [row for row in repo.results_for_run(latest["id"]) if not row["passed"]]
        assert failing, f"{dataset['slug']} latest run should fail at least one rule"
        sample_counts = [
            len(repo.failures_for_run(latest["id"], row["rule_id"], limit=20)) for row in failing
        ]
        assert max(sample_counts) >= 5, "the Failures tab needs a rule with real sample rows"


def test_at_least_one_run_has_no_failures():
    dataset = repo.get_dataset_by_slug("orders_ledger")
    clean = [run for run in seeded_runs(dataset["id"]) if run["failed_rules"] == 0]
    assert clean, "the Failures tab needs a real all-pass run for its empty state"
    assert all(run["quality_score"] == 100.0 for run in clean)


def test_run_timestamps_are_consecutive_daily():
    dataset = repo.get_dataset_by_slug("orders_ledger")
    runs = list(reversed(seeded_runs(dataset["id"])))
    days = [repo.parse_iso(run["started_at"]).date() for run in runs]
    gaps = [(later - earlier).days for earlier, later in zip(days[:-1], days[1:], strict=True)]
    assert set(gaps) == {1}


def test_generated_rows_are_deterministic():
    spec = SPECS_BY_SLUG["billing_transactions"]
    first = build_rows(spec, 7, ANCHOR)
    second = build_rows(spec, 7, ANCHOR)
    assert json.dumps(first, sort_keys=True) == json.dumps(second, sort_keys=True)


def test_generated_rows_differ_between_runs():
    spec = SPECS_BY_SLUG["billing_transactions"]
    quiet = build_rows(spec, 4, ANCHOR)
    degraded = build_rows(spec, 20, ANCHOR)
    assert json.dumps(quiet, sort_keys=True) != json.dumps(degraded, sort_keys=True)
    assert len(quiet) == len(degraded) == ROWS_PER_DATASET


def test_generator_emits_plausible_values():
    spec = SPECS_BY_SLUG["orders_ledger"]
    rows = build_rows(spec, 5, ANCHOR)
    sample = rows[0]
    assert sample["order_id"].startswith("ORD-")
    assert "@" in sample["customer_email"]
    assert isinstance(sample["order_total"], float)
    assert sample["placed_at"].endswith("Z")


def test_seed_moment_is_a_fixed_epoch_not_today():
    """Fresh installs must be reproducible: the anchor never depends on the clock."""
    from datacheck.seed.history import seed_moment

    assert seed_moment(None) == seed_moment(None)
    assert seed_moment(None).date() == seed_epoch_date()
    assert seed_moment(None).hour == 2 and seed_moment(None).minute == 15


def test_generated_rows_ignore_the_wall_clock():
    spec = SPECS_BY_SLUG["billing_transactions"]
    first = json.dumps(build_rows(spec, 6), sort_keys=True)
    second = json.dumps(build_rows(spec, 6), sort_keys=True)
    assert first == second, "build_rows() must be deterministic without an explicit anchor"

    epoch = datetime.combine(seed_epoch_date(), time(2, 15), tzinfo=UTC)
    stamps = [repo.parse_iso(row["captured_at"]) for row in build_rows(spec, 6)]
    assert max(stamps) <= epoch, "no generated timestamp may be later than the seed epoch"
    assert min(stamps) >= epoch - timedelta(days=46), "timestamps stay in the seeded window"


def test_seeded_history_ends_on_the_fixed_epoch():
    for dataset in seeded_datasets():
        latest = seeded_runs(dataset["id"])[0]
        assert repo.parse_iso(latest["started_at"]).date() == seed_epoch_date()


def test_rule_specs_cover_all_three_kinds_per_dataset():
    for spec in DATASET_SPECS:
        kinds = {rule.kind for rule in spec.rules}
        assert kinds == {"null", "range", "unique"}, spec.slug


def test_seed_is_idempotent():
    from datacheck.seed.runner import seed_all

    before = {row["slug"]: repo.count_runs(row["id"]) for row in seeded_datasets()}
    users_before = repo.count_users()
    summary = seed_all(anchor=date(2026, 3, 1))
    assert summary["runs_created"] == 0
    after = {row["slug"]: repo.count_runs(row["id"]) for row in seeded_datasets()}
    assert before == after
    assert repo.count_users() == users_before
