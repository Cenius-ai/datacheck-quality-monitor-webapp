"""Seeded demo accounts.

Passwords are hashed through the exact same helper the sign-in endpoint verifies
with, so the credentials printed on the sign-in card always work.
"""

from __future__ import annotations

import logging

from .. import repositories as repo
from ..auth.passwords import hash_password
from ..config import DEMO_USER_DISPLAY_NAME, DEMO_USER_EMAIL, DEMO_USER_PASSWORD

logger = logging.getLogger(__name__)

DEMO_USERS = (
    {
        "email": DEMO_USER_EMAIL,
        "password": DEMO_USER_PASSWORD,
        "display_name": DEMO_USER_DISPLAY_NAME,
        "role": "lead",
    },
    {
        "email": "demo@datacheck.io",
        "password": "demo1234",
        "display_name": "Ada Whitfield",
        "role": "engineer",
    },
)


def seed_users(created_at: str | None = None) -> int:
    """Create the demo accounts if they are missing. Returns the user count.

    `created_at` is the deterministic seed moment, so two fresh installs produce
    identical rows.
    """
    for user in DEMO_USERS:
        if repo.get_user_by_email(user["email"]) is None:
            repo.create_user(
                user["email"],
                hash_password(user["password"]),
                user["display_name"],
                user["role"],
                created_at=created_at,
            )
            logger.info("datacheck: seeded demo user %s", user["email"])
    return repo.count_users()
