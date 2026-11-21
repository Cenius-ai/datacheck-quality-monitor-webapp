"""Sign-in, sign-out and session lookup with server-side validation."""

from __future__ import annotations

import re
import secrets
import time
from dataclasses import dataclass, field

from .. import repositories as repo
from ..config import (
    LOGIN_MAX_ATTEMPTS,
    LOGIN_WINDOW_SECONDS,
    SESSION_TTL_DAYS,
)
from .passwords import verify_password

EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[A-Za-z]{2,}$")
GENERIC_CREDENTIAL_MESSAGE = "Email or password is incorrect."


@dataclass
class AuthError(Exception):
    """A validated, client-safe authentication failure."""

    status: int
    code: str
    message: str
    fields: dict[str, str] = field(default_factory=dict)

    def as_payload(self) -> dict:
        return {
            "error": {
                "code": self.code,
                "message": self.message,
                "fields": self.fields,
            }
        }


def validate_credentials(payload: dict) -> tuple[str, str]:
    """Server-side validation of a sign-in payload. The UI mirrors these rules."""
    if not isinstance(payload, dict):
        raise AuthError(422, "validation_error", "Send a JSON object.", {})

    email = payload.get("email")
    password = payload.get("password")
    fields: dict[str, str] = {}

    if not isinstance(email, str) or not email.strip():
        fields["email"] = "Email is required."
    elif not EMAIL_PATTERN.match(email.strip()):
        fields["email"] = "Enter a valid email address."

    if not isinstance(password, str) or not password:
        fields["password"] = "Password is required."

    if fields:
        raise AuthError(422, "validation_error", "Check the highlighted fields.", fields)

    return email.strip().lower(), password


def _throttle(keys: list[str]) -> None:
    window = LOGIN_WINDOW_SECONDS
    window_start = int(time.time() // window) * window
    for key in keys:
        count = repo.bump_rate_limit(key, window_start)
        if count > LOGIN_MAX_ATTEMPTS:
            retry_after = window - (int(time.time()) - window_start)
            raise AuthError(
                429,
                "too_many_attempts",
                "Too many sign-in attempts. Try again in "
                f"{max(retry_after, 1) // 60 + 1} minute(s).",
                {},
            )


def sign_in(email: str, password: str, client_ip: str = "unknown") -> tuple[dict, str]:
    """Verify credentials, create a session row and return (user, token)."""
    _throttle([f"ip:{client_ip}", f"email:{email}"])

    user = repo.get_user_by_email(email)
    if user is None or not verify_password(user["password_hash"], password):
        # One non-enumerating message for both unknown email and bad password.
        raise AuthError(401, "invalid_credentials", GENERIC_CREDENTIAL_MESSAGE, {})

    token = secrets.token_urlsafe(32)
    repo.create_session(token, user["id"], SESSION_TTL_DAYS)
    repo.clear_rate_limit(f"email:{email}")
    return (
        {
            "id": user["id"],
            "email": user["email"],
            "display_name": user["display_name"],
            "role": user["role"],
        },
        token,
    )


def sign_out(token: str) -> None:
    if token:
        repo.delete_session(token)


def session_user(token: str | None) -> dict | None:
    """Resolve a session token to its user, honouring expiry."""
    if not token:
        return None
    session = repo.get_session(token)
    if session is None:
        return None
    if session["expires_at"] <= repo.utc_now():
        repo.delete_session(token)
        return None
    return {
        "id": session["user_id"],
        "email": session["email"],
        "display_name": session["display_name"],
        "role": session["role"],
    }
