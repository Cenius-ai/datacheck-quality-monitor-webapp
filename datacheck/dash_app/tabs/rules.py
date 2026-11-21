"""Rules tab: rule table with outcomes, per-rule history, create-rule form."""

from __future__ import annotations

from dash import dcc, html

from ..format import humanize_timestamp, kind_label, rule_parameters


def _result_cell(result: dict | None) -> html.Td:
    if result is None:
        return html.Td(html.Span("not run", className="dc-pill dc-pill--muted"), className="dc-res")
    if result["passed"]:
        return html.Td(html.Span("passed", className="dc-pill dc-pill--pass"), className="dc-res")
    return html.Td(
        [
            html.Span("failed", className="dc-pill dc-pill--fail"),
            html.Span(f"{result['failing_count']:,} rows", className="dc-muted dc-res__count"),
        ],
        className="dc-res",
    )


def rule_table(rules: list[dict], results_by_rule: dict[int, dict], run: dict | None) -> html.Div:
    if not rules:
        return html.Div(
            [
                html.P("No rules are defined for this dataset yet.", className="dc-empty__text"),
                html.P("Create the first rule below.", className="dc-empty__hint"),
            ],
            className="dc-empty",
        )

    header = html.Thead(
        html.Tr(
            [
                html.Th("Rule", scope="col"),
                html.Th("Type", scope="col"),
                html.Th("Column", scope="col"),
                html.Th("Parameters", scope="col"),
                html.Th("State", scope="col"),
                html.Th("Result", scope="col"),
                html.Th("History", scope="col", className="dc-cell--action"),
            ]
        )
    )
    rows = []
    for rule in rules:
        result = results_by_rule.get(rule["id"])
        enabled = bool(rule["enabled"])
        rows.append(
            html.Tr(
                [
                    html.Td(rule["name"], className="dc-cell--strong"),
                    html.Td(html.Span(kind_label(rule["kind"]), className=f"dc-kind dc-kind--{rule['kind']}")),
                    html.Td(html.Code(rule["column_name"], className="dc-code")),
                    html.Td(rule_parameters(rule), className="dc-mono dc-muted"),
                    html.Td(
                        dcc.Checklist(
                            id={"type": "rule-toggle", "index": rule["id"]},
                            options=[{"label": "Enabled", "value": "on"}],
                            value=["on"] if enabled else [],
                            className="dc-switch",
                            labelClassName="dc-switch__label",
                            inputClassName="dc-switch__input",
                        )
                    ),
                    _result_cell(result if enabled else None),
                    html.Td(
                        html.Button(
                            "History",
                            id={"type": "rule-focus", "index": rule["id"]},
                            n_clicks=0,
                            type="button",
                            className="dc-btn dc-btn--row",
                        ),
                        className="dc-cell--action",
                    ),
                ],
                className="dc-row",
            )
        )

    caption = (
        f"Outcomes for run #{run['run_number']} · {humanize_timestamp(run['started_at'])}"
        if run
        else "No run yet"
    )
    return html.Div(
        [
            html.Table([header, html.Tbody(rows)], className="dc-table"),
            html.P(caption, className="dc-table__caption"),
        ]
    )


def history_panel(rule: dict | None, history: list[dict]) -> html.Div:
    if rule is None:
        return html.Div(
            [
                html.P("Pick a rule to see its run history.", className="dc-empty__text"),
                html.P(
                    "Every rule keeps its last 21 outcomes — the strip below fills in as runs complete.",
                    className="dc-empty__hint",
                ),
            ],
            className="dc-empty",
        )

    if not history:
        return html.Div(
            html.P(f"{rule['name']} has not been evaluated yet.", className="dc-empty__text"),
            className="dc-empty",
        )

    strip = html.Div(
        [
            html.Div(
                html.Span(
                    className="dc-history__shape",
                ),
                className=(
                    "dc-history__cell dc-history__cell--pass"
                    if row["passed"]
                    else "dc-history__cell dc-history__cell--fail"
                ),
                title=(
                    f"Run #{row['run_number']} · {humanize_timestamp(row['started_at'])} · "
                    + ("passed" if row["passed"] else f"{row['failing_count']:,} failing rows")
                ),
                **{"aria-label": f"Run {row['run_number']}: {'passed' if row['passed'] else 'failed'}"},
            )
            for row in history
        ],
        className="dc-history__strip",
        role="img",
        **{"aria-label": f"Last {len(history)} outcomes for {rule['name']}"},
    )

    recent = list(reversed(history[-6:]))
    recent_rows = [
        html.Tr(
            [
                html.Td(f"#{row['run_number']}", className="dc-cell--num dc-mono"),
                html.Td(humanize_timestamp(row["started_at"])),
                html.Td(
                    html.Span(
                        "passed" if row["passed"] else "failed",
                        className=f"dc-pill dc-pill--{'pass' if row['passed'] else 'fail'}",
                    )
                ),
                html.Td(f"{row['failing_count']:,}", className="dc-cell--num"),
            ]
        )
        for row in recent
    ]

    return html.Div(
        [
            html.Div(
                [
                    html.H3(rule["name"], className="dc-panel__title"),
                    html.P(
                        f"{kind_label(rule['kind'])} · {rule['column_name']} · "
                        f"{rule_parameters(rule)}",
                        className="dc-panel__sub",
                    ),
                ],
                className="dc-panel__head",
            ),
            html.P(
                f"{len(history)} runs · oldest → newest",
                className="dc-label",
            ),
            strip,
            html.Table(
                [
                    html.Thead(
                        html.Tr(
                            [
                                html.Th("Run", scope="col", className="dc-cell--num"),
                                html.Th("Started", scope="col"),
                                html.Th("Outcome", scope="col"),
                                html.Th("Failing rows", scope="col", className="dc-cell--num"),
                            ]
                        )
                    ),
                    html.Tbody(recent_rows),
                ],
                className="dc-table dc-table--tight",
            ),
        ],
        className="dc-panel",
    )


def create_rule_form(columns: list[str], dataset_name: str) -> html.Div:
    return html.Div(
        [
            html.Div(
                [
                    html.H3("Create a rule", className="dc-panel__title"),
                    html.P(
                        f"Rules are evaluated against the {dataset_name} source rows on the next run.",
                        className="dc-panel__sub",
                    ),
                ],
                className="dc-panel__head",
            ),
            html.Div(
                [
                    html.Div(
                        [
                            html.Label("Rule name", htmlFor="create-rule-name", className="dc-label"),
                            dcc.Input(
                                id="create-rule-name",
                                type="text",
                                className="dc-input",
                                placeholder="Amount is never negative",
                                autoComplete="off",
                            ),
                        ],
                        className="dc-field",
                    ),
                    html.Div(
                        [
                            html.P("Rule type", className="dc-label", id="create-rule-kind-label"),
                            dcc.RadioItems(
                                id="create-rule-kind",
                                options=[
                                    {"label": "Null check", "value": "null"},
                                    {"label": "Range check", "value": "range"},
                                    {"label": "Uniqueness check", "value": "unique"},
                                ],
                                value="null",
                                className="dc-radios dc-radios--inline",
                                labelClassName="dc-radio",
                                inputClassName="dc-radio__input",
                            ),
                        ],
                        className="dc-field",
                        role="group",
                        **{"aria-labelledby": "create-rule-kind-label"},
                    ),
                    html.Div(
                        [
                            html.P("Column", className="dc-label", id="create-rule-column-label"),
                            dcc.RadioItems(
                                id="create-rule-column",
                                options=[{"label": column, "value": column} for column in columns],
                                value=columns[0] if columns else None,
                                className="dc-radios dc-radios--inline",
                                labelClassName="dc-radio",
                                inputClassName="dc-radio__input",
                            ),
                        ],
                        className="dc-field",
                        role="group",
                        **{"aria-labelledby": "create-rule-column-label"},
                    ),
                    html.Div(
                        [
                            html.Label("Minimum", htmlFor="create-rule-min", className="dc-label"),
                            dcc.Input(
                                id="create-rule-min",
                                type="number",
                                step="any",
                                className="dc-input",
                                placeholder="0",
                                inputMode="decimal",
                            ),
                        ],
                        className="dc-field dc-field--narrow",
                    ),
                    html.Div(
                        [
                            html.Label("Maximum", htmlFor="create-rule-max", className="dc-label"),
                            dcc.Input(
                                id="create-rule-max",
                                type="number",
                                step="any",
                                className="dc-input",
                                placeholder="2500",
                                inputMode="decimal",
                            ),
                        ],
                        className="dc-field dc-field--narrow",
                    ),
                ],
                className="dc-form-grid",
            ),
            html.P(
                "Minimum and maximum only apply to range checks; minimum must be lower than maximum.",
                className="dc-hint",
            ),
            html.Div(
                [
                    html.Button(
                        "Create rule",
                        id="create-rule-submit",
                        n_clicks=0,
                        type="button",
                        className="dc-btn dc-btn--primary",
                    ),
                    html.Div(id="create-rule-feedback", className="dc-feedback", role="status"),
                ],
                className="dc-form-actions",
            ),
        ],
        className="dc-panel",
    )
