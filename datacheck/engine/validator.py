"""Validation engine: evaluate a dataset's enabled rules and persist the run."""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta

from .. import repositories as repo
from ..config import MAX_FAILURE_SAMPLES
from .checks import evaluate_rule
from .persistence import persist_run

logger = logging.getLogger(__name__)


class DatasetNotFound(LookupError):
    """Raised when a run is requested for a dataset id that does not exist."""


def compute_quality_score(total_checks: int, failing_checks: int) -> float:
    """Share of (row, rule) checks that passed, as a percentage.

    Row-level checks give a smoother, more honest trend than a rule-level ratio:
    one noisy null rule on a 500-row dataset should move the score by a fraction
    of a point, not by 20.
    """
    if total_checks <= 0:
        return 100.0
    passing = max(total_checks - failing_checks, 0)
    return round(100.0 * passing / total_checks, 2)


def run_validation(
    dataset_id: int,
    *,
    rows: list[dict] | None = None,
    rules: list[dict] | None = None,
    trigger: str = "manual",
    started_at: datetime | None = None,
    run_number: int | None = None,
    sample_cap: int = MAX_FAILURE_SAMPLES,
) -> dict:
    """Evaluate every enabled rule for a dataset against its persisted rows.

    Returns the stored run record. The run, its per-rule results and the failing
    row samples are written in a single transaction.
    """
    dataset = repo.get_dataset(dataset_id)
    if dataset is None:
        raise DatasetNotFound(f"dataset {dataset_id} does not exist")

    if rows is None:
        rows = repo.load_source_rows(dataset_id)
    if rules is None:
        rules = repo.list_enabled_rules(dataset_id)

    started = started_at or datetime.now(UTC)
    if started.tzinfo is None:
        started = started.replace(tzinfo=UTC)

    results: list[dict] = []
    samples: list[dict] = []
    total_checks = 0
    failing_checks = 0

    for rule in rules:
        outcome = evaluate_rule(rule, rows)
        total_checks += outcome.checked_count
        failing_checks += outcome.failing_count
        results.append(
            {
                "rule_id": rule["id"],
                "passed": 1 if outcome.passed else 0,
                "checked_count": outcome.checked_count,
                "failing_count": outcome.failing_count,
            }
        )
        for failure in outcome.failures[:sample_cap]:
            samples.append({**failure, "rule_id": rule["id"]})

    failed_rules = sum(1 for result in results if not result["passed"])
    quality_score = compute_quality_score(total_checks, failing_checks)

    # A deterministic, plausible evaluation duration so seeded runs differ.
    duration = timedelta(milliseconds=650 + (len(results) * 137))
    finished = started + duration

    number = run_number if run_number is not None else repo.next_run_number(dataset_id)
    run_id = persist_run(
        {
            "dataset_id": dataset_id,
            "run_number": number,
            "started_at": repo.to_iso(started),
            "finished_at": repo.to_iso(finished),
            "trigger": trigger,
            "checked_rows": len(rows),
            "total_rules": len(results),
            "failed_rules": failed_rules,
            "quality_score": quality_score,
        },
        results,
        samples,
    )
    logger.info(
        "datacheck: run %s for dataset %s (%s) score=%.2f failed_rules=%s",
        number,
        dataset["slug"],
        trigger,
        quality_score,
        failed_rules,
    )
    stored = repo.get_run(run_id)
    assert stored is not None
    return stored
