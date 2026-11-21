"""Shared reads that turn (dataset, run) selection into render-ready state.

Every tab resolves its data through here, so the three tabs can never disagree
about which dataset or run they are describing.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .. import repositories as repo
from ..config import HISTORY_RUNS


@dataclass
class OverviewState:
    dataset: dict | None = None
    runs: list[dict] = field(default_factory=list)
    run: dict | None = None
    previous: dict | None = None
    results: list[dict] = field(default_factory=list)
    failing_checks: int = 0


@dataclass
class RulesState:
    dataset: dict | None = None
    run: dict | None = None
    rules: list[dict] = field(default_factory=list)
    results_by_rule: dict[int, dict] = field(default_factory=dict)


@dataclass
class FailuresState:
    dataset: dict | None = None
    run: dict | None = None
    results: list[dict] = field(default_factory=list)
    failing_rules: list[dict] = field(default_factory=list)
    selected_rule: dict | None = None
    samples: list[dict] = field(default_factory=list)
    failing_checks: int = 0


def list_datasets() -> list[dict]:
    return repo.list_datasets()


def default_dataset_id() -> int | None:
    datasets = repo.list_datasets()
    return int(datasets[0]["id"]) if datasets else None


def resolve_dataset(dataset_id: int | None) -> dict | None:
    if dataset_id is None:
        dataset_id = default_dataset_id()
    if dataset_id is None:
        return None
    return repo.get_dataset(int(dataset_id))


def resolve_run(dataset_id: int | None, run_id: int | None) -> dict | None:
    """The selected run, repaired to the dataset's latest run when it does not
    belong to the current dataset (e.g. right after switching datasets)."""
    if dataset_id is None:
        return None
    if run_id is not None:
        run = repo.get_run(int(run_id))
        if run is not None and run["dataset_id"] == int(dataset_id):
            return run
    return repo.latest_run(int(dataset_id))


def load_overview(dataset_id: int | None, run_id: int | None) -> OverviewState:
    dataset = resolve_dataset(dataset_id)
    if dataset is None:
        return OverviewState()
    runs = repo.list_runs(int(dataset["id"]), HISTORY_RUNS)
    run = resolve_run(int(dataset["id"]), run_id)
    previous = None
    if run is not None:
        for candidate in runs:
            if candidate["run_number"] < run["run_number"]:
                previous = candidate
                break
    results = repo.results_for_run(run["id"]) if run else []
    return OverviewState(
        dataset=dataset,
        runs=runs,
        run=run,
        previous=previous,
        results=results,
        failing_checks=sum(row["failing_count"] for row in results),
    )


def load_rules(dataset_id: int | None, run_id: int | None) -> RulesState:
    dataset = resolve_dataset(dataset_id)
    if dataset is None:
        return RulesState()
    run = resolve_run(int(dataset["id"]), run_id)
    rules = repo.list_rules(int(dataset["id"]))
    results = repo.results_for_run(run["id"]) if run else []
    return RulesState(
        dataset=dataset,
        run=run,
        rules=rules,
        results_by_rule={row["rule_id"]: row for row in results},
    )


def load_failures(
    dataset_id: int | None, run_id: int | None, rule_id: int | None
) -> FailuresState:
    dataset = resolve_dataset(dataset_id)
    if dataset is None:
        return FailuresState()
    run = resolve_run(int(dataset["id"]), run_id)
    results = repo.results_for_run(run["id"]) if run else []
    failing_rules = [row for row in results if not row["passed"]]
    failing_checks = sum(row["failing_count"] for row in results)

    selected = None
    if failing_rules:
        if rule_id is not None:
            selected = next((row for row in failing_rules if row["rule_id"] == rule_id), None)
        if selected is None:
            selected = failing_rules[0]
    samples = (
        repo.failures_for_run(run["id"], selected["rule_id"], limit=20)
        if run and selected
        else []
    )
    return FailuresState(
        dataset=dataset,
        run=run,
        results=results,
        failing_rules=failing_rules,
        selected_rule=selected,
        samples=samples,
        failing_checks=failing_checks,
    )
