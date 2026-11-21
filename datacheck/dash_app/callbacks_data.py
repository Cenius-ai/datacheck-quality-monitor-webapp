"""Callbacks that render tab content from the shared (dataset, run) selection."""

from __future__ import annotations

from dash import Input, Output, State, callback, no_update

from .. import repositories as repo
from ..dash_app import state as app_state
from .layout import TAB_FAILURES, TAB_OVERVIEW, TAB_RULES
from .tabs import failures as failures_tab
from .tabs import overview as overview_tab
from .tabs import rules as rules_tab


def register() -> None:
    @callback(
        Output("overview-kpis", "children"),
        Output("score-trend", "figure"),
        Output("overview-summary", "children"),
        Output("runs-table", "children"),
        Input("dataset-picker", "value"),
        Input("selected-run", "data"),
        Input("refresh-tick", "data"),
        Input("tabs", "value"),
    )
    def render_overview(dataset_id, run_id, _tick, tab):
        if tab != TAB_OVERVIEW:
            return (no_update, no_update, no_update, no_update)
        data = app_state.load_overview(dataset_id, run_id)
        resolved_id = data.run["id"] if data.run else None
        return (
            overview_tab.kpi_strip(data.run, data.previous, data.failing_checks),
            overview_tab.trend_figure(data.runs, resolved_id),
            overview_tab.run_detail(data.run, data.previous),
            overview_tab.runs_table(data.runs),
        )

    @callback(
        Output("rules-table", "children"),
        Input("dataset-picker", "value"),
        Input("selected-run", "data"),
        Input("refresh-tick", "data"),
        Input("tabs", "value"),
    )
    def render_rules_table(dataset_id, run_id, _tick, tab):
        if tab != TAB_RULES:
            return no_update
        data = app_state.load_rules(dataset_id, run_id)
        return rules_tab.rule_table(data.rules, data.results_by_rule, data.run)

    @callback(
        Output("rule-history", "children"),
        Input("focused-rule", "data"),
        Input("refresh-tick", "data"),
        Input("tabs", "value"),
        State("dataset-picker", "value"),
    )
    def render_rule_history(rule_id, _tick, tab, dataset_id):
        if tab != TAB_RULES:
            return no_update
        rule = repo.get_rule(int(rule_id)) if rule_id else None
        if rule is not None and dataset_id and rule["dataset_id"] != int(dataset_id):
            rule = None
        if rule is None:
            rules = repo.list_rules(int(dataset_id)) if dataset_id else []
            rule = rules[0] if rules else None
        history = repo.rule_history(rule["id"], limit=21) if rule else []
        return rules_tab.history_panel(rule, history)

    @callback(
        Output("create-rule-column", "options"),
        Output("create-rule-column", "value"),
        Input("dataset-picker", "value"),
        Input("tabs", "value"),
        State("create-rule-column", "value"),
    )
    def rule_form_columns(dataset_id, tab, current):
        if tab != TAB_RULES:
            return (no_update, no_update)
        columns = repo.dataset_columns(int(dataset_id)) if dataset_id else []
        options = [{"label": column, "value": column} for column in columns]
        if current in columns:
            return (options, current)
        return (options, columns[0] if columns else None)

    @callback(
        Output("failures-summary", "children"),
        Output("failure-rule-picker", "options"),
        Output("failure-rule-picker", "value"),
        Input("dataset-picker", "value"),
        Input("selected-run", "data"),
        Input("refresh-tick", "data"),
        Input("tabs", "value"),
        State("failure-rule-picker", "value"),
    )
    def render_failures_picker(dataset_id, run_id, _tick, tab, current_rule):
        if tab != TAB_FAILURES:
            return (no_update, no_update, no_update)
        selected = int(current_rule) if isinstance(current_rule, int) else None
        data = app_state.load_failures(dataset_id, run_id, selected)
        options = [
            {
                "label": f"{row['rule_name']} · {row['failing_count']:,} failing",
                "value": row["rule_id"],
            }
            for row in data.failing_rules
        ]
        value = data.selected_rule["rule_id"] if data.selected_rule else None
        return (
            failures_tab.failures_summary(data.run, data.results, data.failing_checks),
            options,
            value,
        )

    @callback(
        Output("failures-table", "children"),
        Input("failure-rule-picker", "value"),
        Input("selected-run", "data"),
        Input("dataset-picker", "value"),
        Input("refresh-tick", "data"),
        Input("tabs", "value"),
    )
    def render_failures_table(rule_id, run_id, dataset_id, _tick, tab):
        if tab != TAB_FAILURES:
            return no_update
        selected = int(rule_id) if isinstance(rule_id, int) else None
        data = app_state.load_failures(dataset_id, run_id, selected)
        return failures_tab.failures_table(
            data.samples, data.selected_rule, data.run, data.failing_rules
        )
