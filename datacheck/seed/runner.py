"""Seed orchestration: schema, demo users, datasets, rows and run history."""

from __future__ import annotations

import logging
from datetime import date

from .. import db
from .. import repositories as repo
from .history import ensure_datasets, seed_history, seed_moment
from .users import seed_users

logger = logging.getLogger(__name__)


def seed_all(anchor: date | None = None) -> dict:
    """Create everything the demo needs. Safe to run repeatedly."""
    db.init_db()
    moment = seed_moment(anchor)
    users = seed_users(created_at=repo.to_iso(moment))
    dataset_ids = ensure_datasets(anchor=anchor)
    runs = seed_history(anchor=anchor)
    summary = {
        "users": users,
        "datasets": len(dataset_ids),
        "runs_created": runs,
        "runs_total": sum(repo.count_runs(dataset_id) for dataset_id in dataset_ids.values()),
    }
    logger.info("datacheck: seed complete %s", summary)
    return summary


def ensure_seeded() -> dict | None:
    """Run the seed only when the database is still empty (called on boot)."""
    db.init_db()
    if repo.count_users() > 0 and repo.list_datasets():
        return None
    logger.info("datacheck: empty database detected, seeding demo data")
    return seed_all()
