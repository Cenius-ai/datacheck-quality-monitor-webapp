"""Read endpoints for rules, their current outcome and their run history."""

from __future__ import annotations

from flask import Blueprint, request

from .. import repositories as repo
from .datasets import require_dataset, require_run, run_summary
from .responses import ApiError, ok

bp = Blueprint("rules_api", __name__, url_prefix="/api")


def rule_payload(rule: dict, result: dict | None = None) -> dict:
    return {
        "id": rule["id"],
        "dataset_id": rule["dataset_id"],
        "name": rule["name"],
        "kind": rule["kind"],
        "column_name": rule["column_name"],
        "params": rule["params"],
        "enabled": bool(rule["enabled"]),
        "created_at": rule["created_at"],
        "result": (
            {
                "run_id": result["run_id"],
                "passed": bool(result["passed"]),
                "checked_count": result["checked_count"],
                "failing_count": result["failing_count"],
            }
            if result
            else None
        ),
    }


@bp.get("/datasets/<int:dataset_id>/rules")
def list_rules(dataset_id: int):
    dataset = require_dataset(dataset_id)
    run_id = request.args.get("run_id", type=int)
    if run_id is not None:
        run = require_run(run_id, dataset_id)
    else:
        run = repo.latest_run(dataset_id)
    results = {row["rule_id"]: row for row in repo.results_for_run(run["id"])} if run else {}
    rules = [rule_payload(rule, results.get(rule["id"])) for rule in repo.list_rules(dataset_id)]
    return ok(
        {
            "dataset": {
                "id": dataset["id"],
                "slug": dataset["slug"],
                "name": dataset["name"],
                "row_count": dataset["row_count"],
            },
            "run": run_summary(run),
            "rules": rules,
        }
    )


@bp.get("/rules/<int:rule_id>/history")
def rule_history(rule_id: int):
    rule = repo.get_rule(rule_id)
    if rule is None:
        raise ApiError(404, "not_found", f"Rule {rule_id} does not exist.")
    history = repo.rule_history(rule_id, limit=21)
    return ok(
        {
            "rule": rule_payload(rule),
            "history": [
                {
                    "run_id": row["run_id"],
                    "run_number": row["run_number"],
                    "started_at": row["started_at"],
                    "passed": bool(row["passed"]),
                    "checked_count": row["checked_count"],
                    "failing_count": row["failing_count"],
                }
                for row in history
            ],
        }
    )
