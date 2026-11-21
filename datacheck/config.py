"""Runtime configuration.

Every value has a working development default so a bare `python3 app.py` on a
fresh clone boots without an .env file. Point DATABASE_URL at Postgres or set
SESSION_SECRET in production.
"""

from __future__ import annotations

import os
from datetime import date
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent


def _load_dotenv(path: Path) -> None:
    """Minimal .env loader (no dependency): existing environment wins.

    The app boots fine without a .env — install.sh writes one with a generated
    SESSION_SECRET, and every value below has a working development default.
    """
    if not path.exists():
        return
    for raw_line in path.read_text().splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


_load_dotenv(BASE_DIR / ".env")

# --- datastore -------------------------------------------------------------
# Relative SQLite file inside the project. DATABASE_URL overrides it wholesale.
DATABASE_URL = os.environ.get("DATABASE_URL") or f"sqlite:///{BASE_DIR / 'datacheck.db'}"

# --- sessions --------------------------------------------------------------
# Flask's secret key. The session token itself is a 256-bit random value stored
# server-side; this key only signs helper state (flash, form tokens).
SESSION_SECRET = os.environ.get("SESSION_SECRET") or "cenius-dev-6f1c9a4b7d2e53810cbf"
SESSION_COOKIE_NAME = os.environ.get("SESSION_COOKIE_NAME") or "datacheck_session"
SESSION_TTL_DAYS = int(os.environ.get("SESSION_TTL_DAYS", "7"))

# --- sign-in throttling ----------------------------------------------------
LOGIN_MAX_ATTEMPTS = int(os.environ.get("LOGIN_MAX_ATTEMPTS", "10"))
LOGIN_WINDOW_SECONDS = int(os.environ.get("LOGIN_WINDOW_SECONDS", "900"))

# --- seeding ---------------------------------------------------------------
# Fixed epoch for the seeded history. Determinism matters more than recency here:
# every fresh install must produce byte-identical run timestamps, scores and
# failing-row samples, so the anchor is a constant rather than `today`.
SEED_EPOCH = os.environ.get("SEED_EPOCH") or "2026-03-01"
ROWS_PER_DATASET = int(os.environ.get("ROWS_PER_DATASET", "500"))
HISTORY_RUNS = int(os.environ.get("HISTORY_RUNS", "21"))
MAX_FAILURE_SAMPLES = int(os.environ.get("MAX_FAILURE_SAMPLES", "20"))
DEMO_USER_EMAIL = "cenius@cenius.ai"
DEMO_USER_NAME = "cenius"
DEMO_USER_PASSWORD = "cenius"
DEMO_USER_DISPLAY_NAME = "Cenius Demo Engineer"

def seed_epoch_date() -> date:
    """The deterministic day the 21-run seeded history ends on."""
    return date.fromisoformat(SEED_EPOCH)


# --- server ----------------------------------------------------------------
PORT = int(os.environ.get("PORT", "8050"))
HOST = os.environ.get("HOST", "0.0.0.0")

# --- design tokens mirrored in assets/style.css ---------------------------
CHART_ACCENT = "#9884f3"
CHART_MUTED = "#5b5b66"
CHART_GRID = "#2d2d34"
CHART_TEXT = "#efeff5"
CHART_FAIL = "#c9302d"
CHART_PASS = "#4ec08b"
CHART_WARN = "#d8a24a"
