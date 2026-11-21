"""The Dash application shell: rail, header, dcc.Tabs and initial tab content."""

from __future__ import annotations

from dash import dcc, html
from flask import has_request_context, request

from .. import repositories as repo
from . import header, state
from .tabs import failures as failures_tab
from .tabs import overview as overview_tab
from .tabs import rules as rules_tab

TAB_OVERVIEW = "overview"
TAB_RULES = "rules"
TAB_FAILURES = "failures"
TAB_VALUES = (TAB_OVERVIEW, TAB_RULES, TAB_FAILURES)


def dataset_picker(datasets: list[dict], selected_id: int | None) -> dcc.RadioItems:
    options = [{"label": row["name"], "value": row["id"]} for row in datasets]
    return dcc.RadioItems(
        id="dataset-picker",
        options=options,
        value=selected_id,
        className="dc-radios",
        labelClassName="dc-radio",
        inputClassName="dc-radio__input",
    )


def _overview_tab(dataset_id: int | None, run_id: int | None) -> html.Div:
    data = state.load_overview(dataset_id, run_id)
    return html.Div(
        [
            html.Div(id="overview-kpis", children=overview_tab.kpi_strip(
                data.run, data.previous, data.failing_checks
            )),
            html.Div(
                [
                    html.Div(
                        [
                            html.Div(
                                [
                                    html.H3("Quality score trend", className="dc-panel__title"),
                                    html.P(
                                        "Quality score across the last 21 runs. Select a point to scope the other tabs.",
                                        className="dc-panel__sub",
                                    ),
                                ],
                                className="dc-panel__head",
                            ),
                            dcc.Graph(
                                id="score-trend",
                                figure=overview_tab.trend_figure(data.runs, data.run["id"] if data.run else None),
                                config={"displayModeBar": False, "responsive": True},
                                className="dc-chart",
                                style={"height": "300px"},
                            ),
                        ],
                        className="dc-panel dc-panel--chart",
                    ),
                    html.Div(
                        [
                            html.H3("Selected run", className="dc-panel__title"),
                            html.Div(id="overview-summary", children=overview_tab.run_detail(
                                data.run, data.previous
                            )),
                        ],
                        className="dc-panel dc-panel--aside",
                    ),
                ],
                className="dc-split",
            ),
            html.Div(
                [
                    html.Div(
                        [
                            html.H3("Recent runs", className="dc-panel__title"),
                            html.P(
                                "Newest first. Select any run to scope the Rules and Failures tabs.",
                                className="dc-panel__sub",
                            ),
                        ],
                        className="dc-panel__head",
                    ),
                    html.Div(id="runs-table", children=overview_tab.runs_table(data.runs)),
                ],
                className="dc-panel",
            ),
        ],
        className="dc-tab",
    )


def _rules_tab(dataset_id: int | None, run_id: int | None) -> html.Div:
    data = state.load_rules(dataset_id, run_id)
    focused_id = data.rules[0]["id"] if data.rules else None
    focused = next((rule for rule in data.rules if rule["id"] == focused_id), None)
    history = repo.rule_history(focused_id, limit=21) if focused_id else []
    columns = repo.dataset_columns(int(data.dataset["id"])) if data.dataset else []
    return html.Div(
        [
            html.Div(
                [
                    html.Div(
                        [
                            html.H3("Rules", className="dc-panel__title"),
                            html.P(
                                "Every rule is evaluated against the stored source rows on each run.",
                                className="dc-panel__sub",
                            ),
                        ],
                        className="dc-panel__head",
                    ),
                    html.Div(id="rules-table", children=rules_tab.rule_table(
                        data.rules, data.results_by_rule, data.run
                    )),
                ],
                className="dc-panel",
            ),
            html.Div(
                [
                    html.Div(id="rule-history", children=rules_tab.history_panel(focused, history)),
                    rules_tab.create_rule_form(columns, data.dataset["name"] if data.dataset else "dataset"),
                ],
                className="dc-split",
            ),
        ],
        className="dc-tab",
    )


def _failures_tab(dataset_id: int | None, run_id: int | None) -> html.Div:
    data = state.load_failures(dataset_id, run_id, None)
    return html.Div(
        [
            html.Div(id="failures-summary", children=failures_tab.failures_summary(
                data.run, data.results, data.failing_checks
            )),
            html.Div(
                [
                    html.Div(
                        [
                            html.Div(
                                [
                                    html.H3("Failing rows", className="dc-panel__title"),
                                    html.P(
                                        "Up to 20 sampled rows per failing rule, with the reason it failed.",
                                        className="dc-panel__sub",
                                    ),
                                ],
                                className="dc-panel__head",
                            ),
                            html.Div(
                                [
                                    html.P("Failing rule", className="dc-label"),
                                    dcc.RadioItems(
                                        id="failure-rule-picker",
                                        options=[
                                            {
                                                "label": f"{row['rule_name']} · {row['failing_count']:,} failing",
                                                "value": row["rule_id"],
                                            }
                                            for row in data.failing_rules
                                        ],
                                        value=data.selected_rule["rule_id"] if data.selected_rule else None,
                                        className="dc-radios dc-radios--stack",
                                        labelClassName="dc-radio",
                                        inputClassName="dc-radio__input",
                                    ),
                                ],
                                className="dc-picker",
                            ),
                            html.Div(
                                id="failures-table",
                                children=failures_tab.failures_table(
                                    data.samples,
                                    data.selected_rule,
                                    data.run,
                                    data.failing_rules,
                                ),
                            ),
                        ],
                        className="dc-panel__body",
                    )
                ],
                className="dc-panel",
            ),
        ],
        className="dc-tab",
    )


def _requested_dataset_id(datasets: list[dict]) -> int | None:
    """The dataset named in the query string (?dataset=), else the first one.

    The layout is served per request, so deep links and a browser refresh restore
    the selected dataset on the server without a URL -> component callback (which
    would make the dataset picker and the address bar depend on each other).
    """
    if has_request_context():
        raw = request.args.get("dataset")
        if raw and raw.isdigit() and any(str(row["id"]) == raw for row in datasets):
            return int(raw)
    return int(datasets[0]["id"]) if datasets else None


def _requested_tab() -> str:
    if has_request_context():
        requested = request.args.get("tab")
        if requested in TAB_VALUES:
            return requested
    return TAB_OVERVIEW


def build_layout() -> html.Div:
    datasets = state.list_datasets()
    dataset_id = _requested_dataset_id(datasets)
    tab_id = _requested_tab()
    run = repo.latest_run(dataset_id) if dataset_id is not None else None
    run_id = run["id"] if run else None
    dataset = repo.get_dataset(dataset_id) if dataset_id is not None else None
    first_rule = repo.list_rules(dataset_id)[:1] if dataset_id is not None else []

    return html.Div(
        [
            dcc.Location(id="url"),
            dcc.Store(id="dataset-store", storage_type="session", data=dataset_id),
            dcc.Store(id="selected-run", storage_type="session", data=run_id),
            dcc.Store(
                id="focused-rule",
                storage_type="session",
                data=first_rule[0]["id"] if first_rule else None,
            ),
            dcc.Store(id="refresh-tick", data=0),
            header.header(),
            html.Div(id="flash", className="dc-flash", role="status", **{"aria-live": "polite"}),
            html.Div(
                [
                    header.rail(dataset_picker(datasets, dataset_id)),
                    html.Main(
                        [
                            header.main_head(
                                dataset["name"] if dataset else "No dataset",
                                dataset["description"] if dataset else "",
                            ),
                            dcc.Tabs(
                                id="tabs",
                                value=tab_id,
                                children=[
                                    dcc.Tab(
                                        label="Quality overview",
                                        value=TAB_OVERVIEW,
                                        children=_overview_tab(dataset_id, run_id),
                                        className="dc-tabbtn",
                                        selected_className="dc-tabbtn--selected",
                                    ),
                                    dcc.Tab(
                                        label="Rules",
                                        value=TAB_RULES,
                                        children=_rules_tab(dataset_id, run_id),
                                        className="dc-tabbtn",
                                        selected_className="dc-tabbtn--selected",
                                    ),
                                    dcc.Tab(
                                        label="Failures",
                                        value=TAB_FAILURES,
                                        children=_failures_tab(dataset_id, run_id),
                                        className="dc-tabbtn",
                                        selected_className="dc-tabbtn--selected",
                                    ),
                                ],
                                colors={
                                    "border": "#2d2d34",
                                    "primary": "#9884f3",
                                    "background": "transparent",
                                },
                                parent_className="dc-tabs",
                                content_className="dc-tabs__content",
                                mobile_breakpoint=600,
                            ),
                        ],
                        className="dc-main",
                    ),
                ],
                className="dc-shell",
            ),
        ],
        className="dc-app",
    )
