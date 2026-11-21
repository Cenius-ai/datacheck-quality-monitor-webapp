"""Consistent JSON envelopes and error handling for the /api/* surface."""

from __future__ import annotations

import logging

from flask import Flask, jsonify
from markupsafe import escape

logger = logging.getLogger(__name__)


class ApiError(Exception):
    """A client-safe API failure carrying an HTTP status and a stable code."""

    def __init__(
        self,
        status: int,
        code: str,
        message: str,
        fields: dict[str, str] | None = None,
    ) -> None:
        super().__init__(message)
        self.status = status
        self.code = code
        self.message = message
        self.fields = fields or {}

    def payload(self) -> dict:
        return {"error": {"code": self.code, "message": self.message, "fields": self.fields}}


def ok(payload: dict | None = None, status: int = 200):
    return jsonify(payload or {}), status


def error(status: int, code: str, message: str, fields: dict[str, str] | None = None):
    return jsonify({"error": {"code": code, "message": message, "fields": fields or {}}}), status


def register_error_handlers(app: Flask) -> None:
    @app.errorhandler(ApiError)
    def _handle_api_error(exc: ApiError):
        return jsonify(exc.payload()), exc.status

    @app.errorhandler(404)
    def _handle_404(_exc):
        from flask import request

        if request.path.startswith("/api/"):
            return error(404, "not_found", "That resource does not exist.")
        return _render_not_found(), 404

    @app.errorhandler(500)
    def _handle_500(exc):
        # Full detail to the log, generic body to the caller.
        logger.exception("datacheck: unhandled error", exc_info=exc)
        from flask import request

        if request.path.startswith("/api/"):
            return error(500, "internal_error", "Something went wrong on our side.")
        return _render_not_found("Something went wrong on our side."), 500


def _render_not_found(message: str = "That page does not exist.") -> str:
    """Plain HTML shell for non-API 404/500s. The message is escaped even though
    every current caller passes a constant, so the helper stays safe if it is
    ever handed a request-derived string."""
    safe_message = escape(message)
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Not found · Datacheck Quality Monitor</title>
<link rel="stylesheet" href="/static/style.css">
</head><body class="dc-plain">
<main class="dc-plain__main">
  <p class="dc-eyebrow">Datacheck Quality Monitor</p>
  <h1 class="dc-plain__title">{safe_message}</h1>
  <p class="dc-muted">Head back to the <a href="/app">quality workspace</a> or <a href="/login">sign in</a>.</p>
</main></body></html>"""
