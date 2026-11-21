"""Read endpoints for run-level results and failing rows."""

from __future__ import annotations

from flask import Blueprint, request

from .. import repositories as repo
from .datasets import require_run, run_summary
from .responses import ApiError, ok

bp = Blueprint("runs_api", __name__, url_prefix="/api")


@bp.get("/runs/<int:run_id>/rule-results")
def rule_results(run_id: int):
    run = require_run(run_id)
    results = repo.results_for_run(run_id)
    return ok(
        {
            "run": run_summary(run),
            "results": [
                {
                    "rule_id": row["rule_id"],
                    "rule_name": row["rule_name"],
                    "kind": row["kind"],
                    "column_name": row["column_name"],
                    "passed": bool(row["passed"]),
                    "checked_count": row["checked_count"],
                    "failing_count": row["failing_count"],
                }
                for row in results
            ],
        }
    )


@bp.get("/runs/<int:run_id>/failures")
def failures(run_id: int):
    run = require_run(run_id)
    rule_id = request.args.get("rule_id", type=int)
    if rule_id is not None and repo.get_rule(rule_id) is None:
        raise ApiError(404, "not_found", f"Rule {rule_id} does not exist.")
    try:
        limit = min(max(int(request.args.get("limit", 20)), 1), 100)
    except (TypeError, ValueError):
        limit = 20

    samples = repo.failures_for_run(run_id, rule_id, limit)
    counts = repo.failure_sample_counts(run_id)
    return ok(
        {
            "run": run_summary(run),
            "rule_id": rule_id,
            "checked_rows": run["checked_rows"],
            "failing_rows": sum(
                row["failing_count"] for row in repo.results_for_run(run_id)
            ),
            "failing_rules": [
                {"rule_id": key, "samples": value} for key, value in sorted(counts.items())
            ],
            "failures": [
                {
                    "row_index": row["row_index"],
                    "column_name": row["column_name"],
                    "value_text": row["value_text"],
                    "reason": row["reason"],
                    "rule_id": row["rule_id"],
                    "rule_name": row["rule_name"],
                }
                for row in samples
            ],
        }
    )
