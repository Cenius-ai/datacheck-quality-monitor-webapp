"""Quality Overview tab: score trend, KPI tiles and the recent-runs table."""

from __future__ import annotations

import plotly.graph_objects as go
from dash import html

from ...config import CHART_ACCENT, CHART_GRID, CHART_TEXT
from ...repositories import parse_iso
from ..format import count_text, delta_text, humanize_timestamp, score_text, score_tone
from ..theme import style_figure

TARGET_SCORE = 95.0


def kpi_strip(run: dict | None, previous: dict | None, failing_checks: int) -> html.Div:
    if run is None:
        return html.Div(
            html.P("No validation runs yet — press Run validation now to create the first one.",
                   className="dc-empty__text"),
            className="dc-empty",
        )

    score = run["quality_score"]
    delta, delta_tone = delta_text(score, previous["quality_score"] if previous else None)
    passed_rules = run["total_rules"] - run["failed_rules"]

    tiles = [
        {
            "label": "Quality score",
            "value": score_text(score),
            "unit": "%",
            "meta": delta,
            "tone": score_tone(score),
            "meta_tone": delta_tone,
        },
        {
            "label": "Rules passing",
            "value": str(passed_rules),
            "unit": f"/ {run['total_rules']}",
            "meta": f"{run['failed_rules']} failing" if run["failed_rules"] else "all green",
            "tone": "fail" if run["failed_rules"] else "pass",
            "meta_tone": "fail" if run["failed_rules"] else "pass",
        },
        {
            "label": "Rows checked",
            "value": count_text(run["checked_rows"]),
            "unit": "rows",
            "meta": f"{count_text(failing_checks)} failing checks",
            "tone": "warn" if failing_checks else "pass",
            "meta_tone": "warn" if failing_checks else "pass",
        },
        {
            "label": "Run",
            "value": f"#{run['run_number']}",
            "unit": "",
            "meta": humanize_timestamp(run["started_at"]),
            "tone": "neutral",
            "meta_tone": "neutral",
        },
    ]

    return html.Div(
        [
            html.Div(
                [
                    html.P(tile["label"], className="dc-kpi__label"),
                    html.P(
                        [
                            html.Span(tile["value"], className="dc-kpi__value"),
                            html.Span(tile["unit"], className="dc-kpi__unit"),
                        ],
                        className="dc-kpi__num",
                    ),
                    html.P(tile["meta"], className=f"dc-kpi__meta dc-tone--{tile['meta_tone']}"),
                ],
                className="dc-kpi",
            )
            for tile in tiles
        ],
        className="dc-kpis",
    )


def _figure_height(points: int) -> int:
    return 300 if points > 1 else 220


def trend_figure(runs: list[dict], selected_run_id: int | None) -> go.Figure:
    ordered = list(reversed(runs))
    figure = go.Figure()
    if not ordered:
        figure.update_layout(
            height=_figure_height(0),
            xaxis=dict(visible=False),
            yaxis=dict(visible=False),
            annotations=[
                dict(
                    text="No runs yet",
                    showarrow=False,
                    font=dict(size=13, color="#9d9da6"),
                    xref="paper",
                    yref="paper",
                    x=0.5,
                    y=0.5,
                )
            ],
        )
        return style_figure(figure)

    timestamps = [parse_iso(run["started_at"]) for run in ordered]
    scores = [run["quality_score"] for run in ordered]
    custom = [
        [
            run["id"],
            run["run_number"],
            run["total_rules"],
            run["failed_rules"],
            humanize_timestamp(run["started_at"]),
        ]
        for run in ordered
    ]

    figure.add_trace(
        go.Scatter(
            x=timestamps,
            y=scores,
            mode="lines+markers",
            name="Quality score",
            line=dict(color=CHART_ACCENT, width=2, shape="linear"),
            marker=dict(size=7, color=CHART_ACCENT, line=dict(width=1.5, color="#0c0c11")),
            customdata=custom,
            hovertemplate=(
                "<b>Run %{customdata[1]}</b> · %{customdata[4]}"
                "<br>Score %{y:.2f}%"
                "<br>%{customdata[2]} rules · %{customdata[3]} failing"
                "<extra></extra>"
            ),
        )
    )

    selected = next((run for run in ordered if run["id"] == selected_run_id), None)
    if selected is not None:
        figure.add_trace(
            go.Scatter(
                x=[parse_iso(selected["started_at"])],
                y=[selected["quality_score"]],
                mode="markers",
                name="Selected run",
                marker=dict(size=14, color=CHART_ACCENT, line=dict(width=2, color=CHART_TEXT)),
                hoverinfo="skip",
                showlegend=False,
            )
        )

    low = max(0.0, min(scores) - 10.0)
    style_figure(figure)
    figure.update_layout(
        height=_figure_height(len(ordered)),
        showlegend=False,
        hovermode="closest",
        margin=dict(l=8, r=8, t=18, b=8),
        xaxis=dict(
            tickformat="%d %b",
            showgrid=False,
            showline=True,
            ticks="outside",
            tickcolor=CHART_GRID,
        ),
        yaxis=dict(
            range=[low, 100.5],
            ticksuffix="%",
            title=dict(text="Quality score", font=dict(size=12, color="#9d9da6")),
        ),
        shapes=[
            dict(
                type="line",
                xref="paper",
                x0=0,
                x1=1,
                yref="y",
                y0=TARGET_SCORE,
                y1=TARGET_SCORE,
                line=dict(color="#4ec08b", width=1, dash="dot"),
            )
        ],
        annotations=[
            dict(
                xref="paper",
                x=1,
                y=TARGET_SCORE,
                yref="y",
                text="target 95%",
                showarrow=False,
                xanchor="right",
                yanchor="bottom",
                font=dict(size=11, color="#4ec08b"),
            )
        ],
    )
    return figure


def runs_table(runs: list[dict]) -> html.Div:
    if not runs:
        return html.Div(
            html.P(
                "No runs recorded for this dataset yet. Press Run validation now to evaluate its rules.",
                className="dc-empty__text",
            ),
            className="dc-empty",
        )

    header = html.Thead(
        html.Tr(
            [
                html.Th("Run", scope="col", className="dc-cell--num"),
                html.Th("Started", scope="col"),
                html.Th("Score", scope="col", className="dc-cell--num"),
                html.Th("Rules passed", scope="col", className="dc-cell--num"),
                html.Th("Trigger", scope="col"),
                html.Th("Select", scope="col", className="dc-cell--action"),
            ]
        )
    )
    body = html.Tbody(
        [
            html.Tr(
                [
                    html.Td(f"#{run['run_number']}", className="dc-cell--num dc-mono"),
                    html.Td(humanize_timestamp(run["started_at"])),
                    html.Td(
                        html.Span(
                            f"{score_text(run['quality_score'])}%",
                            className=f"dc-score dc-tone--{score_tone(run['quality_score'])}",
                        ),
                        className="dc-cell--num",
                    ),
                    html.Td(
                        f"{run['total_rules'] - run['failed_rules']} / {run['total_rules']}",
                        className="dc-cell--num",
                    ),
                    html.Td(
                        html.Span(run["trigger"], className=f"dc-pill dc-pill--{run['trigger']}")
                    ),
                    html.Td(
                        html.Button(
                            "Select",
                            id={"type": "run-pick", "index": run["id"]},
                            n_clicks=0,
                            type="button",
                            className="dc-btn dc-btn--row",
                            **{"aria-label": f"Select run {run['run_number']}"},
                        ),
                        className="dc-cell--action",
                    ),
                ],
                className="dc-row",
            )
            for run in runs
        ]
    )
    return html.Table([header, body], className="dc-table")


def run_detail(run: dict | None, previous: dict | None) -> html.Div:
    if run is None:
        return html.Div(
            html.P("Select a run to inspect it.", className="dc-empty__text"), className="dc-empty"
        )
    try:
        took = (
            parse_iso(run["finished_at"]) - parse_iso(run["started_at"])
        ).total_seconds()
    except (ValueError, TypeError):
        took = 0.0
    rows = [
        ("Run", f"#{run['run_number']}"),
        ("Started", humanize_timestamp(run["started_at"])),
        ("Duration", f"{took * 1000:.0f} ms" if took < 2 else f"{took:.1f} s"),
        ("Trigger", run["trigger"]),
        ("Checked rows", count_text(run["checked_rows"])),
        ("Rules evaluated", f"{run['total_rules']} ({run['failed_rules']} failing)"),
        (
            "Previous score",
            f"{score_text(previous['quality_score'])}%" if previous else "—",
        ),
    ]
    return html.Dl(
        [html.Div([html.Dt(label), html.Dd(value)], className="dc-dl__row") for label, value in rows],
        className="dc-dl",
    )
