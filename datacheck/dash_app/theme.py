"""Shared chart styling for every figure the dashboard builds.

Styling is applied explicitly to each figure rather than through a global
chart-style registry, so no string templating is involved in the chart path at
all. Chart APIs only ever receive hex strings — the CSS palette uses oklch
ramps in a couple of places, which canvas renderers cannot parse.
"""

from __future__ import annotations

import plotly.graph_objects as go

from ..config import CHART_ACCENT, CHART_FAIL, CHART_GRID, CHART_PASS, CHART_TEXT, CHART_WARN

COLORWAY = [CHART_ACCENT, CHART_WARN, CHART_PASS, CHART_FAIL]
FONT_FAMILY = "Manrope, Segoe UI, system-ui, sans-serif"
AXIS_TEXT = "#9d9da6"
HOVER_BG = "#16161d"
HOVER_BORDER = "#2d2d34"


def style_figure(figure: go.Figure) -> go.Figure:
    """Apply the committed chart look: transparent surfaces, hairline grid, Manrope."""
    figure.update_layout(
        colorway=list(COLORWAY),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(family=FONT_FAMILY, size=13, color=CHART_TEXT),
        hoverlabel=dict(
            bgcolor=HOVER_BG,
            bordercolor=HOVER_BORDER,
            font=dict(family=FONT_FAMILY, size=12, color=CHART_TEXT),
        ),
    )
    figure.update_xaxes(
        gridcolor=CHART_GRID,
        zeroline=False,
        linecolor=CHART_GRID,
        tickfont=dict(size=12, color=AXIS_TEXT),
        title=dict(font=dict(size=12, color=AXIS_TEXT)),
    )
    figure.update_yaxes(
        gridcolor=CHART_GRID,
        zeroline=False,
        linecolor=CHART_GRID,
        tickfont=dict(size=12, color=AXIS_TEXT),
        title=dict(font=dict(size=12, color=AXIS_TEXT)),
    )
    return figure
