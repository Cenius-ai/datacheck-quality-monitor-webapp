"""Sign-in / sign-out endpoints."""

from __future__ import annotations

from flask import Blueprint, jsonify, request

from ..auth import service
from ..auth.service import AuthError
from ..config import SESSION_COOKIE_NAME, SESSION_TTL_DAYS

bp = Blueprint("auth_api", __name__, url_prefix="/api/auth")


@bp.post("/signin")
def signin():
    payload = request.get_json(silent=True)
    if payload is None:
        payload = request.form.to_dict()
    try:
        email, password = service.validate_credentials(payload)
        user, token = service.sign_in(email, password, request.remote_addr or "unknown")
    except AuthError as exc:
        return jsonify(exc.as_payload()), exc.status

    response = jsonify({"user": user})
    response.set_cookie(
        SESSION_COOKIE_NAME,
        token,
        max_age=SESSION_TTL_DAYS * 24 * 3600,
        httponly=True,
        samesite="Lax",
        path="/",
        # No `secure` flag: the app is served over plain http in local/preview use.
    )
    response.headers["Cache-Control"] = "no-store"
    return response, 200


@bp.post("/signout")
def signout():
    service.sign_out(request.cookies.get(SESSION_COOKIE_NAME, ""))
    response = jsonify({"ok": True})
    response.delete_cookie(SESSION_COOKIE_NAME, path="/")
    response.headers["Cache-Control"] = "no-store"
    return response, 200
