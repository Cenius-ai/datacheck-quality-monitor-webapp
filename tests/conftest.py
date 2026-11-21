"""Test fixtures: one seeded throwaway SQLite database for the whole session."""

from __future__ import annotations

import os
import tempfile
from datetime import date
from pathlib import Path

import pytest

# The config module reads these at import time, so set them before any
# datacheck import happens (conftest is imported before test modules).
_TEST_DB = Path(tempfile.mkdtemp(prefix="datacheck-tests-")) / "test.db"
os.environ["DATABASE_URL"] = f"sqlite:///{_TEST_DB}"
os.environ["SESSION_SECRET"] = "cenius-dev-test-only-session-secret"
os.environ["LOGIN_MAX_ATTEMPTS"] = "50"

ANCHOR = date(2026, 3, 1)


@pytest.fixture(scope="session", autouse=True)
def seeded_database():
    """Seed once with a fixed anchor date so runs are reproducible."""
    from datacheck.seed.runner import seed_all

    seed_all(anchor=ANCHOR)
    yield


@pytest.fixture(scope="session")
def dash_module(seeded_database):
    """The real entrypoint module (Flask app + Dash app fully wired)."""
    import app as app_module

    return app_module


@pytest.fixture()
def client(dash_module):
    return dash_module.server.test_client()


@pytest.fixture()
def auth_client(client):
    """A client with the standard demo session already established."""
    response = client.post(
        "/api/auth/signin",
        json={"email": "cenius@cenius.ai", "password": "cenius"},
    )
    assert response.status_code == 200, response.get_json()
    return client


@pytest.fixture()
def dataset_ids():
    from datacheck import repositories as repo

    return {row["slug"]: row["id"] for row in repo.list_datasets()}
