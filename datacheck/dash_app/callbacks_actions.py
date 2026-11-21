"""Callbacks for the write paths: run validation, create rule, toggle rule."""

from __future__ import annotations

import logging

from dash import ALL, Input, Output, State, callback, ctx, html, no_update

from .. import repositories as repo
from ..api.responses import ApiError
from ..api.validation import validate_rule_payload
from ..engine.validator import DatasetNotFound, run_validation

logger = logging.getLogger(__name__)


def flash(message: str, tone: str = "ok") -> html.Div:
    glyph = {"ok": "▸", "err": "▸", "warn": "▸"}.get(tone, "▸")
    return html.Div(
        [html.Span(glyph, className="dc-flash__glyph"), html.Span(message)],
        className=f"dc-flash__msg dc-flash__msg--{tone}",
    )


def register() -> None:
    @callback(
        Output("flash", "children", allow_duplicate=True),
        Output("refresh-tick", "data", allow_duplicate=True),
        Output("selected-run", "data", allow_duplicate=True),
        Input("run-validation", "n_clicks"),
        State("dataset-picker", "value"),
        State("refresh-tick", "data"),
        prevent_initial_call=True,
        running=[
            (Output("run-validation", "disabled"), True, False),
            (Output("run-validation", "children"), "Running checks…", "Run validation now"),
        ],
    )
    def run_now(_n_clicks, dataset_id, tick):
        if not dataset_id:
            return flash("Pick a dataset before running validation.", "err"), no_update, no_update
        try:
            run = run_validation(int(dataset_id), trigger="manual")
        except DatasetNotFound:
            return flash("That dataset no longer exists.", "err"), no_update, no_update
        except Exception:  # noqa: BLE001 - boundary: log the detail, show a safe message
            logger.exception("datacheck: manual validation failed for dataset %s", dataset_id)
            return (
                flash("Validation could not complete. Nothing was saved — try again.", "err"),
                no_update,
                no_update,
            )
        message = (
            f"Run #{run['run_number']} finished · score {run['quality_score']:.2f}% · "
            f"{run['failed_rules']} of {run['total_rules']} rules failing"
        )
        return flash(message, "ok" if run["failed_rules"] == 0 else "warn"), (tick or 0) + 1, run["id"]

    @callback(
        Output("create-rule-feedback", "children"),
        Output("flash", "children", allow_duplicate=True),
        Output("refresh-tick", "data", allow_duplicate=True),
        Output("create-rule-name", "value"),
        Output("create-rule-min", "value"),
        Output("create-rule-max", "value"),
        Input("create-rule-submit", "n_clicks"),
        State("create-rule-name", "value"),
        State("create-rule-kind", "value"),
        State("create-rule-column", "value"),
        State("create-rule-min", "value"),
        State("create-rule-max", "value"),
        State("dataset-picker", "value"),
        State("refresh-tick", "data"),
        prevent_initial_call=True,
        running=[(Output("create-rule-submit", "disabled"), True, False)],
    )
    def create_rule(
        _n_clicks, name, kind, column, minimum, maximum, dataset_id, tick
    ):
        keep = no_update
        if not dataset_id:
            return (
                html.P("Pick a dataset first.", className="dc-error"),
                no_update,
                no_update,
                keep,
                keep,
                keep,
            )
        payload = {
            "dataset_id": int(dataset_id),
            "name": name,
            "kind": kind,
            "column_name": column,
            "params": {"min": minimum, "max": maximum},
        }
        try:
            fields = validate_rule_payload(payload, int(dataset_id))
            rule_id = repo.create_rule(
                fields["dataset_id"],
                fields["name"],
                fields["kind"],
                fields["column_name"],
                fields["params"],
            )
        except ApiError as exc:
            messages = [
                html.P(message, className="dc-error") for message in exc.fields.values()
            ] or [html.P(exc.message, className="dc-error")]
            return (html.Div(messages), no_update, no_update, keep, keep, keep)
        except Exception:  # noqa: BLE001 - boundary: log detail, safe message to the user
            logger.exception("datacheck: rule creation failed")
            return (
                html.P("The rule could not be saved. Try again.", className="dc-error"),
                no_update,
                no_update,
                keep,
                keep,
                keep,
            )

        created = repo.get_rule(rule_id)
        name_text = created["name"] if created else (name or "rule")
        return (
            html.P(f'"{name_text}" saved. It will be evaluated on the next run.',
                   className="dc-success"),
            flash(f'Rule "{name_text}" created.', "ok"),
            (tick or 0) + 1,
            "",
            "",
            "",
        )

    @callback(
        Output("flash", "children", allow_duplicate=True),
        Output("refresh-tick", "data", allow_duplicate=True),
        Input({"type": "rule-toggle", "index": ALL}, "value"),
        State("dataset-picker", "value"),
        State("refresh-tick", "data"),
        prevent_initial_call=True,
    )
    def toggle_rule(values, dataset_id, tick):
        trigger = ctx.triggered_id
        if not isinstance(trigger, dict) or trigger.get("type") != "rule-toggle":
            return (no_update, no_update)
        rule_id = int(trigger["index"])
        rule = repo.get_rule(rule_id)
        if rule is None:
            return (flash("That rule no longer exists.", "err"), no_update)
        if dataset_id and rule["dataset_id"] != int(dataset_id):
            return (flash("That rule belongs to another dataset.", "err"), no_update)

        rules = repo.list_rules(rule["dataset_id"])
        position = next((index for index, row in enumerate(rules) if row["id"] == rule_id), None)
        if position is None or not isinstance(values, list) or position >= len(values):
            return (no_update, no_update)
        desired = bool(values[position])
        if desired == bool(rule["enabled"]):
            # Widget re-render, not a real click.
            return (no_update, no_update)
        repo.set_rule_enabled(rule_id, desired)
        state = "enabled" if desired else "disabled"
        return (flash(f'Rule "{rule["name"]}" {state}.', "ok"), (tick or 0) + 1)
