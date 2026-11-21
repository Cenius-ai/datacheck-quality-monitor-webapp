"""Password hashing — the single code path used by both the seed and sign-in."""

from __future__ import annotations

from werkzeug.security import check_password_hash, generate_password_hash


def hash_password(password: str) -> str:
    """Hash with scrypt (werkzeug's default, memory-hard, per-password salt)."""
    return generate_password_hash(password, method="scrypt")


def verify_password(password_hash: str, password: str) -> bool:
    if not password_hash or not password:
        return False
    try:
        return check_password_hash(password_hash, password)
    except ValueError:
        # A malformed/legacy hash in the database must never authenticate anyone.
        return False
