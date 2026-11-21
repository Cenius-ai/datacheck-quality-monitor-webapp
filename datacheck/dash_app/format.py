"""Human-readable formatting shared by the tabs (all rendered server-side)."""

from __future__ import annotations

from datetime import UTC, datetime

from ..repositories import parse_iso

MONTHS = ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")


def humanize_timestamp(value: str | None) -> str:
    """'Today 02:17' / 'Yesterday 02:20' / '3 Mar 02:15' — never a raw ISO string."""
    if not value:
        return "—"
    try:
        moment = parse_iso(value).astimezone(UTC)
    except (ValueError, TypeError):
        return "—"
    today = datetime.now(UTC).date()
    delta_days = (today - moment.date()).days
    clock = moment.strftime("%H:%M")
    if delta_days == 0:
        return f"Today {clock}"
    if delta_days == 1:
        return f"Yesterday {clock}"
    if 1 < delta_days < 7:
        return f"{delta_days} days ago"
    return f"{moment.day} {MONTHS[moment.month - 1]} {clock}"


def score_text(value: float | None) -> str:
    if value is None:
        return "—"
    return f"{value:.2f}"


def count_text(value: int | None) -> str:
    if value is None:
        return "—"
    return f"{int(value):,}"


def score_tone(score: float | None) -> str:
    if score is None:
        return "neutral"
    if score >= 95:
        return "pass"
    if score >= 85:
        return "warn"
    return "fail"


def rule_parameters(rule: dict) -> str:
    """Render a rule's parameters as a short human phrase."""
    params = rule.get("params") or {}
    if rule["kind"] == "range":
        minimum, maximum = params.get("min"), params.get("max")
        if minimum is not None and maximum is not None:
            return f"{_format_bound(minimum)} – {_format_bound(maximum)}"
        if minimum is not None:
            return f"≥ {_format_bound(minimum)}"
        if maximum is not None:
            return f"≤ {_format_bound(maximum)}"
        return "any value"
    if rule["kind"] == "unique":
        return "no duplicates"
    return "no nulls"


def _format_bound(value) -> str:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return str(value)
    if number.is_integer():
        return f"{int(number):,}"
    return f"{number:,.2f}"


def kind_label(kind: str) -> str:
    return {"null": "Null", "range": "Range", "unique": "Unique"}.get(kind, kind.title())


def delta_text(current: float | None, previous: float | None) -> tuple[str, str]:
    """Return (text, tone) for a score delta versus the previous run."""
    if current is None or previous is None:
        return ("first run", "neutral")
    change = current - previous
    if abs(change) < 0.005:
        return ("no change vs previous", "neutral")
    arrow = "▲" if change > 0 else "▼"
    tone = "pass" if change > 0 else "fail"
    return (f"{arrow} {abs(change):.2f} pts vs previous", tone)
