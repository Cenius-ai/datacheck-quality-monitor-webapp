"""Callbacks that keep the selection state, the URL and the pickers in sync.

The layout is rendered per request, so the query string -> UI direction is
handled on the server (deep links and refreshes restore the dataset and tab
without a callback). The opposite direction — UI -> URL — is this module's job:
the picked dataset is mirrored into a dcc.Store and written back into the address
bar. Keeping the two directions in different layers is what keeps the callback
graph acyclic (Dash refuses component pairs that feed each other).
"""

from __future__ import annotations

from dash import ALL, Input, Output, State, callback, ctx, html, no_update
from flask import request

from .. import repositories as repo
from ..auth import service
from ..config import SESSION_COOKIE_NAME
from . import state as app_state
from .format import humanize_timestamp, score_text, score_tone
from .layout import TAB_VALUES


def register() -> None:
    @callback(Output("dataset-store", "data"), Input("dataset-picker", "value"))
    def mirror_dataset(dataset_id):
        """Mirror the picker into the shared store the tabs and the URL read from."""
        return dataset_id

    @callback(
        Output("url", "search"),
        Input("dataset-store", "data"),
        State("tabs", "value"),
        prevent_initial_call=True,
    )
    def persist_selection_to_url(dataset_id, tab):
        """Write ?dataset= (and the active tab) into the address bar.

        A page refresh then re-renders this dataset from the server, and the URL
        is shareable. `search` is only ever written here — nothing reads it — so
        the graph stays acyclic.
        """
        if not dataset_id:
            return no_update
        dataset = repo.get_dataset(int(dataset_id))
        if dataset is None:
            return no_update
        tab_value = tab if tab in TAB_VALUES else "overview"
        return f"?tab={tab_value}&dataset={int(dataset_id)}"

    @callback(
        Output("nav-overview", "href"),
        Output("nav-rules", "href"),
        Output("nav-failures", "href"),
        Input("dataset-picker", "value"),
    )
    def view_links(dataset_id):
        suffix = f"&dataset={int(dataset_id)}" if dataset_id else ""
        return (
            f"/app?tab=overview{suffix}",
            f"/app?tab=rules{suffix}",
            f"/app?tab=failures{suffix}",
        )

    @callback(
        Output("nav-overview", "className"),
        Output("nav-rules", "className"),
        Output("nav-failures", "className"),
        Input("tabs", "value"),
    )
    def nav_active(tab):
        base = "dc-nav__link"
        active = f"{base} {base}--active"
        return (
            active if tab == "overview" else base,
            active if tab == "rules" else base,
            active if tab == "failures" else base,
        )

    @callback(Output("current-user", "children"), Input("url", "pathname"))
    def current_user(_pathname):
        user = service.session_user(request.cookies.get(SESSION_COOKIE_NAME))
        if user is None:
            return "session ended"
        return f"{user['display_name']} · {user['email']}"

    @callback(
        Output("selected-run", "data"),
        Input("dataset-picker", "value"),
        Input({"type": "run-pick", "index": ALL}, "n_clicks"),
        Input("score-trend", "clickData"),
    )
    def select_run(dataset_id, _clicks, click_data):
        trigger = ctx.triggered_id
        if isinstance(trigger, dict) and trigger.get("type") == "run-pick":
            clicked = ctx.triggered[0]["value"] if ctx.triggered else None
            if not clicked:
                # The table was re-rendered and the button's counter reset: not a click.
                return no_update
            return int(trigger["index"])
        if trigger == "score-trend":
            points = (click_data or {}).get("points") or []
            if points and points[0].get("customdata"):
                return int(points[0]["customdata"][0])
            return no_update
        if trigger == "dataset-picker" or trigger is None:
            latest = repo.latest_run(dataset_id) if dataset_id else None
            return latest["id"] if latest else None
        return no_update

    @callback(
        Output("focused-rule", "data"),
        Input({"type": "rule-focus", "index": ALL}, "n_clicks"),
        prevent_initial_call=True,
    )
    def focus_rule(_clicks):
        trigger = ctx.triggered_id
        if not isinstance(trigger, dict) or trigger.get("type") != "rule-focus":
            return no_update
        clicked = ctx.triggered[0]["value"] if ctx.triggered else None
        if not clicked:
            return no_update
        return int(trigger["index"])

    @callback(
        Output("dataset-meta", "children"),
        Output("dataset-title", "children"),
        Output("dataset-description", "children"),
        Input("dataset-picker", "value"),
        Input("refresh-tick", "data"),
    )
    def dataset_meta(dataset_id, _tick):
        dataset = app_state.resolve_dataset(dataset_id)
        if dataset is None:
            return (no_update, no_update, no_update)
        rules = repo.list_rules(int(dataset["id"]))
        latest = repo.latest_run(int(dataset["id"]))
        enabled = sum(1 for rule in rules if rule["enabled"])
        meta = [
            _meta_row("Rows", f"{repo.count_source_rows(int(dataset['id'])):,}"),
            _meta_row("Rules", f"{enabled} enabled / {len(rules)}"),
            _meta_row(
                "Latest score",
                f"{score_text(latest['quality_score'])}%" if latest else "no runs yet",
            ),
            _meta_row("Runs", f"{repo.count_runs(int(dataset['id']))}"),
        ]
        return meta, dataset["name"], dataset["description"] or ""

    @callback(
        Output("run-context", "children"),
        Input("selected-run", "data"),
        Input("dataset-picker", "value"),
        Input("refresh-tick", "data"),
    )
    def run_context(run_id, dataset_id, _tick):
        run = app_state.resolve_run(dataset_id, run_id)
        if run is None:
            return _span("No runs yet", "dc-muted")
        return [
            _span(f"Run #{run['run_number']}", "dc-runctx__run"),
            _span(humanize_timestamp(run["started_at"]), "dc-runctx__time"),
            _span(
                f"{score_text(run['quality_score'])}%",
                f"dc-runctx__score dc-tone--{score_tone(run['quality_score'])}",
            ),
        ]


def _span(text: str, class_name: str):
    return html.Span(text, className=class_name)


def _meta_row(label: str, value: str):
    return html.Div(
        [html.Span(label, className="dc-metarow__label"), html.Span(value, className="dc-metarow__value")],
        className="dc-metarow",
    )
