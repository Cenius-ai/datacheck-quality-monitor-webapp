"""Failures tab: failing-rule picker and the sampled failing rows."""

from __future__ import annotations

from dash import html

from ..format import count_text, humanize_timestamp


def failures_summary(run: dict | None, results: list[dict], failing_checks: int) -> html.Div:
    if run is None:
        return html.Div(
            html.P("No run selected.", className="dc-empty__text"), className="dc-empty"
        )

    failed = [row for row in results if not row["passed"]]
    stats = [
        ("Checked rows", count_text(run["checked_rows"])),
        ("Failing rows", count_text(failing_checks)),
        ("Failing rules", f"{len(failed)} / {run['total_rules']}"),
        ("Run", f"#{run['run_number']} · {humanize_timestamp(run['started_at'])}"),
    ]
    return html.Div(
        [
            html.Div(
                [
                    html.P(label, className="dc-stat__label"),
                    html.P(value, className="dc-stat__value"),
                ],
                className="dc-stat",
            )
            for label, value in stats
        ],
        className="dc-stats",
    )


def failures_table(
    failures: list[dict], rule: dict | None, run: dict | None, failing_rules: list[dict]
) -> html.Div:
    if run is None:
        return html.Div(
            html.P("No run selected.", className="dc-empty__text"), className="dc-empty"
        )
    if not failing_rules:
        return html.Div(
            [
                html.P("No failures in this run", className="dc-empty__title"),
                html.P(
                    "Every enabled rule passed against the source rows in this run. "
                    "Pick an earlier run to review a regression.",
                    className="dc-empty__text",
                ),
            ],
            className="dc-empty dc-empty--good",
        )
    if not failures:
        return html.Div(
            html.P("No sampled rows for this rule.", className="dc-empty__text"), className="dc-empty"
        )

    header = html.Thead(
        html.Tr(
            [
                html.Th("Row", scope="col", className="dc-cell--num"),
                html.Th("Column", scope="col"),
                html.Th("Bad value", scope="col"),
                html.Th("Why it failed", scope="col"),
            ]
        )
    )
    body = html.Tbody(
        [
            html.Tr(
                [
                    html.Td(f"{row['row_index']:,}", className="dc-cell--num dc-mono"),
                    html.Td(html.Code(row["column_name"], className="dc-code")),
                    html.Td(
                        html.Span(
                            row["value_text"] if row["value_text"] is not None else "(missing)",
                            className=(
                                "dc-value"
                                if row["value_text"] is not None
                                else "dc-value dc-value--null"
                            ),
                        )
                    ),
                    html.Td(row["reason"], className="dc-muted"),
                ],
                className="dc-row",
            )
            for row in failures
        ]
    )
    caption = (
        f"First {len(failures)} of {rule['failing_count']:,} failing rows sampled from run "
        f"#{run['run_number']}."
        if rule
        else ""
    )
    return html.Div(
        [html.Table([header, body], className="dc-table"), html.P(caption, className="dc-table__caption")],
    )
