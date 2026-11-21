"""Deterministic synthetic source data.

The generator is a pure function of (dataset spec, run index): the same seed
always produces byte-identical row payloads, so a fresh install is reproducible
and re-running the seed can never drift the demo data. Defects are injected from
a second RNG keyed by the run index, which is how the seeded history gets a
believable mix of clean and dirty days without any randomness at render time.
"""

from __future__ import annotations

import random
from datetime import UTC, datetime, time, timedelta

from ..config import seed_epoch_date

ISO = "%Y-%m-%dT%H:%M:%SZ"

FIRST_NAMES = (
    "Maya", "Tobias", "Priya", "Elena", "Marcus", "Sofia", "Ibrahim", "Hana",
    "Diego", "Aisling", "Ravi", "Noor", "Lukas", "Amara", "Jonas", "Yuki",
    "Camila", "Oliver", "Zara", "Mateo", "Ines", "Ethan", "Leila", "Kofi",
)
LAST_NAMES = (
    "Okafor", "Lindqvist", "Raman", "Vasquez", "Bell", "Moreau", "Haddad", "Tanaka",
    "Ferreira", "Byrne", "Chandra", "Aziz", "Weber", "Diallo", "Novak", "Sato",
    "Rossi", "Whitfield", "Khan", "Alvarez", "Costa", "Mercer", "Nasser", "Mensah",
)
DOMAINS = (
    "northwind.io", "brightlane.co", "heliostack.dev", "quarry-labs.com",
    "tidewater.app", "kelvinlogistics.com", "nimbusdata.io", "atlas-retail.co",
)
COUNTRIES = ("US", "DE", "GB", "IN", "BR", "JP", "FR", "AU", "CA", "NL")
PLANS = ("free", "free", "starter", "growth", "scale")
ORDER_STATUS = ("paid", "paid", "paid", "fulfilled", "pending", "refunded")
TXN_STATUS = ("captured", "captured", "captured", "refunded", "pending", "failed")
CURRENCIES = ("USD", "USD", "USD", "USD", "EUR", "GBP", "CAD")


def _email(rng: random.Random, index: int) -> str:
    first = FIRST_NAMES[index % len(FIRST_NAMES)]
    last = LAST_NAMES[(index * 7 + rng.randrange(len(LAST_NAMES))) % len(LAST_NAMES)]
    domain = DOMAINS[rng.randrange(len(DOMAINS))]
    suffix = "" if rng.random() < 0.6 else f"{rng.randrange(2, 98)}"
    return f"{first.lower()}.{last.lower()}{suffix}@{domain}"


def _timestamp(rng: random.Random, anchor: datetime, max_days: int = 60) -> str:
    moment = anchor - timedelta(
        days=rng.randrange(max_days), hours=rng.randrange(24), minutes=rng.randrange(60)
    )
    return moment.strftime(ISO)


def _orders_rows(rng: random.Random, anchor: datetime, count: int) -> list[dict]:
    rows = []
    for index in range(count):
        rows.append(
            {
                "order_id": f"ORD-2025-{10240 + index:05d}",
                "customer_email": _email(rng, index),
                "order_total": round(rng.uniform(9.5, 2380.0), 2),
                "currency": CURRENCIES[rng.randrange(len(CURRENCIES))],
                "status": ORDER_STATUS[rng.randrange(len(ORDER_STATUS))],
                "placed_at": _timestamp(rng, anchor),
            }
        )
    return rows


def _signup_rows(rng: random.Random, anchor: datetime, count: int) -> list[dict]:
    rows = []
    for index in range(count):
        rows.append(
            {
                "user_id": f"USR-{rng.randrange(16 ** 8):08x}",
                "email": _email(rng, index),
                "age": rng.randint(18, 74),
                "country": COUNTRIES[rng.randrange(len(COUNTRIES))],
                "plan": PLANS[rng.randrange(len(PLANS))],
                "signed_up_at": _timestamp(rng, anchor, max_days=90),
            }
        )
    return rows


def _transaction_rows(rng: random.Random, anchor: datetime, count: int) -> list[dict]:
    rows = []
    for _ in range(count):
        rows.append(
            {
                "txn_id": f"TXN-{rng.randrange(16 ** 10):010x}".upper(),
                "amount": round(rng.uniform(-140.0, 4180.0), 2),
                "currency": CURRENCIES[rng.randrange(len(CURRENCIES))],
                "merchant_id": f"MER-{rng.randint(10000, 99999)}",
                "status": TXN_STATUS[rng.randrange(len(TXN_STATUS))],
                "captured_at": _timestamp(rng, anchor, max_days=45),
            }
        )
    return rows


BUILDERS = {
    "orders_ledger": _orders_rows,
    "signup_cohort": _signup_rows,
    "billing_transactions": _transaction_rows,
}


def _pick_indices(rng: random.Random, count: int, size: int) -> list[int]:
    if count <= 0:
        return []
    return rng.sample(range(size), min(count, size))


def _apply_defect(
    rows: list[dict], rng: random.Random, column: str, kind: str, count: int, bounds: dict
) -> None:
    size = len(rows)
    if kind == "null":
        for index in _pick_indices(rng, count, size):
            rows[index][column] = None
        return
    if kind == "out_of_range":
        minimum = bounds.get("min")
        maximum = bounds.get("max")
        for index in _pick_indices(rng, count, size):
            if maximum is not None and rng.random() < 0.75:
                rows[index][column] = round(float(maximum) * rng.uniform(1.02, 1.9), 2)
            elif minimum is not None:
                rows[index][column] = round(float(minimum) - rng.uniform(12.0, 480.0), 2)
        return
    if kind == "duplicate":
        pairs = min(count, size // 2)
        sources = _pick_indices(rng, pairs, size)
        remaining = [index for index in range(size) if index not in set(sources)]
        targets = rng.sample(remaining, min(pairs, len(remaining)))
        for source, target in zip(sources, targets, strict=True):
            rows[target][column] = rows[source][column]
        return
    raise ValueError(f"Unknown defect kind: {kind}")


def build_rows(spec, run_index: int, anchor: datetime | None = None) -> list[dict]:
    """Build the 500-row snapshot for one dataset at one point in its history.

    With no anchor the fixed SEED_EPOCH is used, so payloads are byte-identical
    on every install and in every process (no dependence on the wall clock).
    """
    anchor = anchor or datetime.combine(seed_epoch_date(), time(2, 15), tzinfo=UTC)
    if anchor.tzinfo is None:
        anchor = anchor.replace(tzinfo=UTC)

    rng = random.Random(spec.generator_seed)
    rows = BUILDERS[spec.slug](rng, anchor, spec.row_count)

    defect_rng = random.Random(spec.generator_seed * 977 + run_index)
    bounds_by_column = {
        rule.column: rule.params for rule in spec.rules if rule.kind == "range"
    }
    for column, kind, count in spec.defect_plan(run_index):
        _apply_defect(rows, defect_rng, column, kind, count, bounds_by_column.get(column, {}))
    return rows
