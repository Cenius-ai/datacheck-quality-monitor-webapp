"""Read endpoints for datasets and their validation runs."""

from __future__ import annotations

from flask import Blueprint, request

from .. import repositories as repo
from .responses import ApiError, ok

bp = Blueprint("datasets_api", __name__, url_prefix="/api")


def dataset_payload(dataset: dict) -> dict:
    latest = repo.latest_run(dataset["id"])
    return {
        "id": dataset["id"],
        "slug": dataset["slug"],
        "name": dataset["name"],
        "description": dataset["description"],
        "row_count": dataset["row_count"],
        "rule_count": dataset.get("rule_count", len(repo.list_rules(dataset["id"]))),
        "created_at": dataset["created_at"],
        "latest_run": run_summary(latest) if latest else None,
    }


def run_summary(run: dict | None) -> dict | None:
    if not run:
        return None
    return {
        "id": run["id"],
        "dataset_id": run["dataset_id"],
        "run_number": run["run_number"],
        "started_at": run["started_at"],
        "finished_at": run["finished_at"],
        "trigger": run["trigger"],
        "checked_rows": run["checked_rows"],
        "total_rules": run["total_rules"],
        "failed_rules": run["failed_rules"],
        "quality_score": run["quality_score"],
    }


def require_dataset(dataset_id: int) -> dict:
    dataset = repo.get_dataset(dataset_id)
    if dataset is None:
        raise ApiError(404, "not_found", f"Dataset {dataset_id} does not exist.")
    return dataset


def require_run(run_id: int, dataset_id: int | None = None) -> dict:
    run = repo.get_run(run_id)
    if run is None or (dataset_id is not None and run["dataset_id"] != dataset_id):
        raise ApiError(404, "not_found", f"Run {run_id} does not exist.")
    return run


@bp.get("/datasets")
def list_datasets():
    datasets = [dataset_payload(row) for row in repo.list_datasets()]
    return ok({"datasets": datasets})


@bp.get("/datasets/<int:dataset_id>/runs")
def list_runs(dataset_id: int):
    dataset = require_dataset(dataset_id)
    try:
        limit = min(max(int(request.args.get("limit", 21)), 1), 200)
    except (TypeError, ValueError):
        limit = 21
    runs = [run_summary(run) for run in repo.list_runs(dataset_id, limit)]
    return ok({"dataset": dataset_payload(dataset), "runs": runs})
