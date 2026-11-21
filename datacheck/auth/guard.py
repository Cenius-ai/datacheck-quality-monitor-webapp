"""Session guard for the HTML shell and every data endpoint.

Only sign-in, the sign-in page, the health probe and static assets are public.
Everything else — the /app shell, Dash's own callback endpoints and /api/* —
requires a valid server-side session.
"""

from __future__ import annotations

import logging
from urllib.parse import quote

from flask import Flask, g, jsonify, redirect, request

from ..config import SESSION_COOKIE_NAME
from . import service

logger = logging.getLogger(__name__)

PUBLIC_PATHS = {"/login", "/api/auth/signin", "/health"}
PUBLIC_PREFIXES = ("/static/", "/favicon.ico")
MUTATING_METHODS = {"POST", "PUT", "PATCH", "DELETE"}


def _same_origin() -> bool:
    """Reject cross-site writes (defence in depth on top of SameSite=Lax)."""
    origin = request.headers.get("Origin") or request.headers.get("Referer")
    if not origin:
        return True
    host = request.headers.get("Host", "")
    from urllib.parse import urlparse

    return urlparse(origin).netloc == host


def install_guards(app: Flask) -> None:
    @app.before_request
    def _guard():
        path = request.path
        if path in PUBLIC_PATHS or path.startswith(PUBLIC_PREFIXES):
            return None

        g.user = service.session_user(request.cookies.get(SESSION_COOKIE_NAME))

        if path == "/":
            return redirect("/app/" if g.user else "/login")

        is_api = path.startswith("/api/")
        if is_api and request.method in MUTATING_METHODS and not _same_origin():
            return jsonify(
                {"error": {"code": "cross_origin", "message": "Cross-site request rejected.", "fields": {}}}
            ), 403

        if g.user is None:
            if is_api:
                return jsonify(
                    {
                        "error": {
                            "code": "unauthenticated",
                            "message": "Sign in to use the Datacheck API.",
                            "fields": {},
                        }
                    }
                ), 401
            if path == "/app" or path.startswith("/app/"):
                target = path + (f"?{request.query_string.decode()}" if request.query_string else "")
                return redirect(f"/login?next={quote(target, safe='')}")

        return None
