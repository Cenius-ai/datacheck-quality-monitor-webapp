"""Pure rule checks: null, range and uniqueness.

Each check takes the rows (list of payload dicts) and returns a CheckOutcome with
the number of rows checked plus one failure record per offending row (already
capped by the caller). No database access here, which keeps the engine testable
and lets the history seeder evaluate a historical snapshot of the rows.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field
from typing import Any

RULE_KINDS = ("null", "range", "unique")


@dataclass
class CheckOutcome:
    checked_count: int
    failures: list[dict[str, Any]] = field(default_factory=list)

    @property
    def failing_count(self) -> int:
        return len(self.failures)

    @property
    def passed(self) -> bool:
        return not self.failures


def _is_blank(value: Any) -> bool:
    return value is None or (isinstance(value, str) and value.strip() == "")


def format_value(value: Any) -> str | None:
    """Human-readable rendering of a raw cell value (None means a missing value)."""
    if value is None:
        return None
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, float):
        return f"{value:,.2f}"
    if isinstance(value, int):
        return f"{value:,}"
    return str(value)


def _failure(row_index: int, column: str, value: Any, reason: str) -> dict[str, Any]:
    return {
        "row_index": row_index,
        "column_name": column,
        "value_text": format_value(value),
        "reason": reason,
    }


def check_null(rows: Iterable[dict], column: str) -> CheckOutcome:
    outcome = CheckOutcome(checked_count=0)
    for index, row in enumerate(rows):
        outcome.checked_count += 1
        value = row.get(column)
        if _is_blank(value):
            outcome.failures.append(
                _failure(index, column, value, f"{column} is missing (null or blank)")
            )
    return outcome


def _coerce_number(value: Any) -> float | None:
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value.strip())
        except ValueError:
            return None
    return None


def check_range(rows: Iterable[dict], column: str, minimum=None, maximum=None) -> CheckOutcome:
    """Range check. Missing values are skipped (a null rule owns those); a
    non-numeric value present in the column is itself a failure."""
    outcome = CheckOutcome(checked_count=0)
    lower = float(minimum) if minimum is not None else None
    upper = float(maximum) if maximum is not None else None
    for index, row in enumerate(rows):
        outcome.checked_count += 1
        value = row.get(column)
        if _is_blank(value):
            continue
        number = _coerce_number(value)
        if number is None:
            outcome.failures.append(
                _failure(index, column, value, f"{column} is not numeric ({format_value(value)})")
            )
            continue
        if lower is not None and number < lower:
            outcome.failures.append(
                _failure(
                    index,
                    column,
                    value,
                    f"{format_value(number)} is below the minimum of {format_value(lower)}",
                )
            )
        elif upper is not None and number > upper:
            outcome.failures.append(
                _failure(
                    index,
                    column,
                    value,
                    f"{format_value(number)} is above the maximum of {format_value(upper)}",
                )
            )
    return outcome


def check_uniqueness(rows: Iterable[dict], column: str) -> CheckOutcome:
    """Uniqueness check. Missing values are skipped; every row participating in a
    duplicated value is counted once, with the occurrence total in the reason."""
    values = [row.get(column) for row in rows]
    counts: dict[str, int] = {}
    for value in values:
        if _is_blank(value):
            continue
        key = str(value)
        counts[key] = counts.get(key, 0) + 1

    outcome = CheckOutcome(checked_count=0)
    for index, value in enumerate(values):
        outcome.checked_count += 1
        if _is_blank(value):
            continue
        occurrences = counts.get(str(value), 0)
        if occurrences > 1:
            outcome.failures.append(
                _failure(
                    index,
                    column,
                    value,
                    f"{format_value(value)} is duplicated ({occurrences} rows share this value)",
                )
            )
    return outcome


def evaluate_rule(rule: dict, rows: list[dict]) -> CheckOutcome:
    """Dispatch a stored rule record to its check."""
    kind = rule["kind"]
    column = rule["column_name"]
    params = rule.get("params") or {}
    if kind == "null":
        return check_null(rows, column)
    if kind == "range":
        return check_range(rows, column, params.get("min"), params.get("max"))
    if kind == "unique":
        return check_uniqueness(rows, column)
    raise ValueError(f"Unsupported rule kind: {kind!r}")
