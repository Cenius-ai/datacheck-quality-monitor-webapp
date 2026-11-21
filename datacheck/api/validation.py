"""Server-side validation shared by every rule write path."""

from __future__ import annotations

from .. import repositories as repo
from ..engine.checks import RULE_KINDS
from .responses import ApiError

MAX_RULE_NAME = 120


def _as_number(value) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str) and value.strip():
        try:
            return float(value.strip())
        except ValueError:
            return None
    return None


def validate_rule_payload(payload: dict, dataset_id: int) -> dict:
    """Validate a create-rule payload; returns the normalised fields.

    The same checks the create form applies client-side are re-applied here, so a
    hand-rolled request cannot create a rule the engine cannot evaluate.
    """
    if not isinstance(payload, dict):
        raise ApiError(422, "validation_error", "Send a JSON object.")

    dataset = repo.get_dataset(dataset_id)
    if dataset is None:
        raise ApiError(404, "not_found", f"Dataset {dataset_id} does not exist.")

    fields: dict[str, str] = {}

    name = payload.get("name")
    if not isinstance(name, str) or not name.strip():
        fields["name"] = "Give the rule a name."
    elif len(name.strip()) > MAX_RULE_NAME:
        fields["name"] = f"Keep the name under {MAX_RULE_NAME} characters."

    kind = payload.get("kind")
    if not isinstance(kind, str) or kind not in RULE_KINDS:
        fields["kind"] = "Choose a rule type: null, range or uniqueness."

    columns = repo.dataset_columns(dataset_id)
    column = payload.get("column_name")
    if not isinstance(column, str) or not column.strip():
        fields["column_name"] = "Choose the column to check."
    elif column.strip() not in columns:
        fields["column_name"] = f"{column.strip()} is not a column in {dataset['name']}."

    params: dict = {}
    raw_params = payload.get("params") or {}
    if not isinstance(raw_params, dict):
        fields["params"] = "Range parameters must be an object."
        raw_params = {}

    if kind == "range":
        minimum = _as_number(raw_params.get("min"))
        maximum = _as_number(raw_params.get("max"))
        if raw_params.get("min") not in (None, "") and minimum is None:
            fields["min"] = "Minimum must be a number."
        if raw_params.get("max") not in (None, "") and maximum is None:
            fields["max"] = "Maximum must be a number."
        if minimum is None and maximum is None and "min" not in fields and "max" not in fields:
            fields["min"] = "Give the range a minimum, a maximum, or both."
        if minimum is not None and maximum is not None and minimum >= maximum:
            fields["min"] = "Minimum must be less than the maximum."
        params = {
            "min": minimum if minimum is not None else None,
            "max": maximum if maximum is not None else None,
        }

    if isinstance(name, str) and name.strip():
        for existing in repo.list_rules(dataset_id):
            if existing["name"].strip().lower() == name.strip().lower():
                fields["name"] = "A rule with this name already exists for this dataset."
                break

    if fields:
        raise ApiError(422, "validation_error", "Check the highlighted fields.", fields)

    return {
        "dataset_id": dataset_id,
        "name": name.strip(),
        "kind": kind,
        "column_name": column.strip(),
        "params": params,
    }


def validate_rule_patch(payload: dict) -> bool:
    """Validate a PATCH body; returns the requested enabled state."""
    if not isinstance(payload, dict) or "enabled" not in payload:
        raise ApiError(422, "validation_error", "Provide the `enabled` flag.")
    enabled = payload["enabled"]
    if isinstance(enabled, bool):
        return enabled
    if isinstance(enabled, int) and enabled in (0, 1):
        return bool(enabled)
    if isinstance(enabled, str) and enabled.lower() in ("true", "false"):
        return enabled.lower() == "true"
    raise ApiError(422, "validation_error", "`enabled` must be true or false.", {"enabled": "Must be a boolean."})
