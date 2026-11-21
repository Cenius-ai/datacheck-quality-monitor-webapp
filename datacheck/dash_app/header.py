"""The signed-in shell header: brand, identity, run context and actions."""

from __future__ import annotations

from dash import html


def brand() -> html.Div:
    return html.Div(
        [
            html.Span("◆", className="dc-brand__glyph", **{"aria-hidden": "true"}),
            html.Div(
                [
                    html.H1("Datacheck Quality Monitor", className="dc-brand__title"),
                    html.P(
                        "Rules, results and failing rows for warehouse datasets",
                        className="dc-brand__sub",
                    ),
                ],
                className="dc-brand__text",
            ),
        ],
        className="dc-brand",
    )


def identity() -> html.Div:
    return html.Div(
        [
            html.Div(
                [
                    html.Span("Signed in as", className="dc-label"),
                    html.Span(id="current-user", children="…", className="dc-identity__name"),
                ],
                className="dc-identity__text",
            ),
            html.Form(
                html.Button("Sign out", type="submit", className="dc-btn dc-btn--ghost"),
                action="/signout",
                method="post",
                className="dc-signout",
            ),
        ],
        className="dc-identity",
    )


def header() -> html.Header:
    return html.Header([brand(), identity()], className="dc-header")


def main_head(dataset_name: str, dataset_description: str) -> html.Div:
    return html.Div(
        [
            html.Div(
                [
                    html.H2(dataset_name, id="dataset-title", className="dc-main__title"),
                    html.P(dataset_description or "", id="dataset-description", className="dc-main__sub"),
                ],
                className="dc-main__titles",
            ),
            html.Div(
                [
                    html.Div(id="run-context", className="dc-runctx"),
                    html.Button(
                        "Run validation now",
                        id="run-validation",
                        n_clicks=0,
                        type="button",
                        className="dc-btn dc-btn--primary",
                    ),
                ],
                className="dc-main__actions",
            ),
        ],
        className="dc-main__head",
    )


def rail(picker) -> html.Aside:
    return html.Aside(
        [
            html.Div(
                [
                    html.Label("Dataset", htmlFor="dataset-picker", className="dc-label"),
                    picker,
                    html.Div(id="dataset-meta", className="dc-rail__meta"),
                ],
                className="dc-rail__section",
            ),
            html.Nav(
                [
                    html.P("Views", className="dc-label"),
                    html.A(
                        [html.Span("▸", className="dc-nav__glyph"), "Quality overview"],
                        id="nav-overview",
                        href="/app?tab=overview",
                        className="dc-nav__link dc-nav__link--active",
                    ),
                    html.A(
                        [html.Span("▸", className="dc-nav__glyph"), "Rules"],
                        id="nav-rules",
                        href="/app?tab=rules",
                        className="dc-nav__link",
                    ),
                    html.A(
                        [html.Span("▸", className="dc-nav__glyph"), "Failures"],
                        id="nav-failures",
                        href="/app?tab=failures",
                        className="dc-nav__link",
                    ),
                ],
                className="dc-rail__section dc-nav",
                **{"aria-label": "Workspace views"},
            ),
            html.Div(
                [
                    html.P("How scoring works", className="dc-label"),
                    html.P(
                        "A run evaluates every enabled rule against the dataset's stored rows. "
                        "The quality score is the share of row checks that passed.",
                        className="dc-rail__note",
                    ),
                ],
                className="dc-rail__section dc-rail__section--note",
            ),
        ],
        className="dc-rail",
        **{"aria-label": "Dataset filters"},
    )
