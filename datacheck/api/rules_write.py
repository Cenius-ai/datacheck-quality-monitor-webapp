"""Write endpoints: run validation now, create a rule, enable/disable a rule."""

from __future__ import annotations

import logging

from flask import Blueprint, request

from .. import repositories as repo
from ..engine.validator import DatasetNotFound, run_validation
from .datasets import require_dataset, run_summary
from .responses import ApiError, ok
from .rules import rule_payload
from .validation import validate_rule_patch, validate_rule_payload

logger = logging.getLogger(__name__)

bp = Blueprint("writes_api", __name__, url_prefix="/api")


@bp.post("/datasets/<int:dataset_id>/runs")
def create_run(dataset_id: int):
    require_dataset(dataset_id)
    try:
        run = run_validation(dataset_id, trigger="manual")
    except DatasetNotFound as exc:
        raise ApiError(404, "not_found", str(exc)) from exc
    payload = run_summary(run) or {}
    results = repo.results_for_run(run["id"])
    return ok(
        {
            "run": payload,
            "results": [
                {
                    "rule_id": row["rule_id"],
                    "rule_name": row["rule_name"],
                    "passed": bool(row["passed"]),
                    "checked_count": row["checked_count"],
                    "failing_count": row["failing_count"],
                }
                for row in results
            ],
        },
        status=201,
    )


@bp.post("/rules")
def create_rule():
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        raise ApiError(422, "validation_error", "Send a JSON object.")
    dataset_id = payload.get("dataset_id")
    try:
        dataset_id = int(dataset_id)
    except (TypeError, ValueError) as exc:
        raise ApiError(
            422, "validation_error", "Provide a numeric dataset_id.", {"dataset_id": "Required."}
        ) from exc

    fields = validate_rule_payload(payload, dataset_id)
    try:
        rule_id = repo.create_rule(
            fields["dataset_id"],
            fields["name"],
            fields["kind"],
            fields["column_name"],
            fields["params"],
        )
    except Exception as exc:  # noqa: BLE001 - translate the unique constraint into a 422
        if "UNIQUE" in str(exc).upper():
            raise ApiError(
                422,
                "validation_error",
                "Check the highlighted fields.",
                {"name": "A rule with this name already exists for this dataset."},
            ) from exc
        raise
    rule = repo.get_rule(rule_id)
    assert rule is not None
    return ok({"rule": rule_payload(rule)}, status=201)


@bp.patch("/rules/<int:rule_id>")
def patch_rule(rule_id: int):
    rule = repo.get_rule(rule_id)
    if rule is None:
        raise ApiError(404, "not_found", f"Rule {rule_id} does not exist.")
    payload = request.get_json(silent=True)
    enabled = validate_rule_patch(payload)

    requested_dataset = (payload or {}).get("dataset_id")
    if requested_dataset is not None:
        try:
            requested_dataset = int(requested_dataset)
        except (TypeError, ValueError) as exc:
            raise ApiError(422, "validation_error", "dataset_id must be numeric.") from exc
        if requested_dataset != rule["dataset_id"]:
            raise ApiError(404, "not_found", f"Rule {rule_id} does not exist in that dataset.")

    repo.set_rule_enabled(rule_id, enabled)
    updated = repo.get_rule(rule_id)
    assert updated is not None
    return ok({"rule": rule_payload(updated)})
