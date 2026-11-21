"""The three demo datasets, their rules and their daily defect profiles."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from ..config import ROWS_PER_DATASET


@dataclass(frozen=True)
class RuleSpec:
    name: str
    kind: str
    column: str
    params: dict


@dataclass(frozen=True)
class DatasetSpec:
    slug: str
    name: str
    description: str
    generator_seed: int
    columns: tuple[str, ...]
    rules: tuple[RuleSpec, ...]
    profile: str
    row_count: int = ROWS_PER_DATASET

    def defect_plan(self, run_index: int) -> list[tuple[str, str, int]]:
        """(column, defect kind, count) tuples for one day of this dataset."""
        return DEFECT_PROFILES[self.profile](run_index)


# --- defect profiles -------------------------------------------------------
# "stable": small day-to-day noise, quality sits in a tight band near 100.
# "regression": the transaction feed degrades over the last three days.
def _stable_orders(run_index: int) -> list[tuple[str, str, int]]:
    if run_index <= 3:
        # A clean start to the history: every rule passes, so the Failures tab
        # demonstrates its "no failures in this run" state on a real run.
        return [
            ("customer_email", "null", 0),
            ("order_total", "null", 0),
            ("order_total", "out_of_range", 0),
            ("status", "null", 0),
            ("order_id", "duplicate", 0),
        ]
    return [
        ("customer_email", "null", 4 + (run_index * 3) % 6),
        ("order_total", "null", 0 if run_index % 4 else 2),
        ("order_total", "out_of_range", 1 if run_index % 5 == 0 else 0),
        ("status", "null", 0),
        ("order_id", "duplicate", 0),
    ]


def _stable_signups(run_index: int) -> list[tuple[str, str, int]]:
    return [
        ("email", "null", 3 + (run_index * 5) % 7),
        ("age", "null", 0 if run_index % 3 else 2),
        ("age", "out_of_range", 1 if run_index % 7 == 0 else 0),
        ("email", "duplicate", 2 if run_index % 5 == 0 else 0),
        ("user_id", "duplicate", 0),
    ]


# day 19/20/21 of the billing feed: percent-level breakage, not a flat line
_REGRESSION_DAYS = {
    19: [("amount", "out_of_range", 190), ("amount", "null", 24), ("currency", "null", 130),
         ("merchant_id", "null", 60), ("txn_id", "duplicate", 45)],
    20: [("amount", "out_of_range", 208), ("amount", "null", 29), ("currency", "null", 141),
         ("merchant_id", "null", 66), ("txn_id", "duplicate", 49)],
    21: [("amount", "out_of_range", 187), ("amount", "null", 22), ("currency", "null", 128),
         ("merchant_id", "null", 58), ("txn_id", "duplicate", 44)],
}


def _regression_transactions(run_index: int) -> list[tuple[str, str, int]]:
    if run_index in _REGRESSION_DAYS:
        return list(_REGRESSION_DAYS[run_index])
    drift = run_index % 4
    return [
        ("amount", "out_of_range", 2 + drift),
        ("amount", "null", 1),
        ("currency", "null", 1),
        ("merchant_id", "null", 1),
        ("txn_id", "duplicate", 0),
    ]


DEFECT_PROFILES: dict[str, Callable[[int], list[tuple[str, str, int]]]] = {
    "stable_orders": _stable_orders,
    "stable_signups": _stable_signups,
    "regression": _regression_transactions,
}


DATASET_SPECS: tuple[DatasetSpec, ...] = (
    DatasetSpec(
        slug="billing_transactions",
        name="Billing transactions",
        description="Payment provider transaction feed mirrored hourly into the billing warehouse.",
        generator_seed=63914,
        columns=("txn_id", "amount", "currency", "merchant_id", "status", "captured_at"),
        rules=(
            RuleSpec("Transaction ID is unique", "unique", "txn_id", {}),
            RuleSpec("Amount between -250 and 5,000", "range", "amount", {"min": -250, "max": 5000}),
            RuleSpec("Amount is present", "null", "amount", {}),
            RuleSpec("Currency is present", "null", "currency", {}),
            RuleSpec("Merchant ID is present", "null", "merchant_id", {}),
        ),
        profile="regression",
    ),
    DatasetSpec(
        slug="orders_ledger",
        name="Orders ledger",
        description="Nightly export of the commerce order ledger, synced from the storefront into the warehouse.",
        generator_seed=84021,
        columns=("order_id", "customer_email", "order_total", "currency", "status", "placed_at"),
        rules=(
            RuleSpec("Order ID is unique", "unique", "order_id", {}),
            RuleSpec("Customer email is present", "null", "customer_email", {}),
            RuleSpec("Order total between 0 and 2,500", "range", "order_total", {"min": 0, "max": 2500}),
            RuleSpec("Order total is present", "null", "order_total", {}),
            RuleSpec("Status is present", "null", "status", {}),
        ),
        profile="stable_orders",
    ),
    DatasetSpec(
        slug="signup_cohort",
        name="Signup cohort",
        description="Weekly product signups with profile attributes and plan attribution.",
        generator_seed=11507,
        columns=("user_id", "email", "age", "country", "plan", "signed_up_at"),
        rules=(
            RuleSpec("User ID is unique", "unique", "user_id", {}),
            RuleSpec("Age between 13 and 120", "range", "age", {"min": 13, "max": 120}),
            RuleSpec("Email is present", "null", "email", {}),
            RuleSpec("Email is unique", "unique", "email", {}),
            RuleSpec("Age is present", "null", "age", {}),
        ),
        profile="stable_signups",
    ),
)

SPECS_BY_SLUG = {spec.slug: spec for spec in DATASET_SPECS}
