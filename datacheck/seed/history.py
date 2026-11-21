"""Seed the datasets, their rules, their source rows and their run history.

Everything here is idempotent: datasets, rules and source rows are only created
when missing, and history seeding is skipped for a dataset that already has its
21 runs.
"""

from __future__ import annotations

import logging
import random
from datetime import UTC, date, datetime, time, timedelta

from .. import repositories as repo
from ..config import HISTORY_RUNS, seed_epoch_date
from ..engine.validator import run_validation
from .datasets import DATASET_SPECS, DatasetSpec
from .generator import build_rows

logger = logging.getLogger(__name__)


def seed_moment(anchor: date | None) -> datetime:
    """The deterministic moment the seeded history ends on (SEED_EPOCH by default)."""
    day = anchor or seed_epoch_date()
    return datetime.combine(day, time(2, 15), tzinfo=UTC)


def ensure_datasets(specs: tuple[DatasetSpec, ...] = DATASET_SPECS, anchor: date | None = None) -> dict[str, int]:
    """Create missing datasets, rules and the current source-row snapshot."""
    moment = seed_moment(anchor)
    dataset_ids: dict[str, int] = {}
    for spec in specs:
        dataset = repo.get_dataset_by_slug(spec.slug)
        created_at = repo.to_iso(moment)
        if dataset is None:
            dataset_id = repo.create_dataset(
                spec.slug,
                spec.name,
                spec.description,
                spec.row_count,
                spec.generator_seed,
                created_at=created_at,
            )
            logger.info("datacheck: created dataset %s", spec.slug)
        else:
            dataset_id = int(dataset["id"])
        dataset_ids[spec.slug] = dataset_id

        existing_rules = {rule["name"] for rule in repo.list_rules(dataset_id)}
        for rule in spec.rules:
            if rule.name not in existing_rules:
                repo.create_rule(
                    dataset_id,
                    rule.name,
                    rule.kind,
                    rule.column,
                    rule.params,
                    created_at=created_at,
                )

        if repo.count_source_rows(dataset_id) != spec.row_count:
            repo.replace_source_rows(dataset_id, build_rows(spec, HISTORY_RUNS, moment))
            logger.info("datacheck: wrote %s source rows for %s", spec.row_count, spec.slug)
    return dataset_ids


def _run_started_at(anchor: datetime, run_index: int, runs: int, spec: DatasetSpec) -> datetime:
    day = anchor.date() - timedelta(days=runs - run_index)
    jitter = random.Random(spec.generator_seed + run_index).randrange(0, 55)
    return datetime.combine(day, time(2, 15), tzinfo=UTC) + timedelta(minutes=jitter)


def seed_history(
    specs: tuple[DatasetSpec, ...] = DATASET_SPECS,
    anchor: date | None = None,
    runs: int = HISTORY_RUNS,
) -> int:
    """Evaluate every rule once per daily run, oldest first."""
    moment = seed_moment(anchor)
    created = 0
    for spec in specs:
        dataset = repo.get_dataset_by_slug(spec.slug)
        if dataset is None:
            raise RuntimeError(f"dataset {spec.slug} must exist before seeding history")
        dataset_id = int(dataset["id"])
        if repo.count_runs(dataset_id) >= runs:
            continue
        rules = repo.list_enabled_rules(dataset_id)
        for run_index in range(1, runs + 1):
            rows = build_rows(spec, run_index, moment)
            run_validation(
                dataset_id,
                rows=rows,
                rules=rules,
                trigger="seed",
                started_at=_run_started_at(moment, run_index, runs, spec),
                run_number=run_index,
            )
            created += 1
        logger.info("datacheck: seeded %s runs for %s", runs, spec.slug)
    return created
