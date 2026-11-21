"""Single-transaction persistence for a validation run.

A run is only meaningful if its header, its per-rule results and its failing-row
samples land together, so all three writes share one connection/transaction.
"""

from __future__ import annotations

from collections.abc import Iterable

from ..db import connect


def persist_run(
    run_fields: dict,
    results: Iterable[dict],
    samples: Iterable[dict],
) -> int:
    """Insert a run plus its results and samples atomically. Returns the run id."""
    result_rows = [dict(row) for row in results]
    sample_rows = [dict(row) for row in samples]
    with connect() as conn:
        inserted = conn.execute(
            """
            INSERT INTO validation_runs
                (dataset_id, run_number, started_at, finished_at, "trigger",
                 checked_rows, total_rules, failed_rules, quality_score)
            VALUES
                (:dataset_id, :run_number, :started_at, :finished_at, :trigger,
                 :checked_rows, :total_rules, :failed_rules, :quality_score)
            """,
            run_fields,
        )
        run_id = int(inserted.lastrowid)
        if result_rows:
            conn.execute(
                """
                INSERT INTO rule_results (run_id, rule_id, passed, checked_count, failing_count)
                VALUES (:run_id, :rule_id, :passed, :checked_count, :failing_count)
                """,
                [{"run_id": run_id, **row} for row in result_rows],
            )
        if sample_rows:
            conn.execute(
                """
                INSERT INTO failing_rows
                    (run_id, rule_id, row_index, column_name, value_text, reason)
                VALUES
                    (:run_id, :rule_id, :row_index, :column_name, :value_text, :reason)
                """,
                [{"run_id": run_id, **row} for row in sample_rows],
            )
    return run_id
