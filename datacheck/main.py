"""Flask application factory, page routes and the Dash wiring."""

from __future__ import annotations

import logging
from pathlib import Path

from flask import Flask, current_app, redirect, render_template, request

from . import db
from .api import register_api
from .auth import guard, service
from .config import (
    DEMO_USER_EMAIL,
    DEMO_USER_PASSWORD,
    SESSION_COOKIE_NAME,
    SESSION_SECRET,
)
from .seed.runner import ensure_seeded

logger = logging.getLogger(__name__)

PACKAGE_DIR = Path(__file__).resolve().parent
STATIC_DIR = PACKAGE_DIR / "static"
TEMPLATE_DIR = PACKAGE_DIR / "templates"

# Dash inlines its renderer bootstrap; the CSP below allows exactly the hashes
# Dash reports for its own inline scripts (see _content_security_policy).
INDEX_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
  <head>
    {%metas%}
    <title>{%title%}</title>
    {%favicon%}
    <meta name="description" content="Datacheck Quality Monitor — validation rule results, failing rows and quality score trends for warehouse datasets.">
    <link rel="icon" type="image/svg+xml" href="/static/favicon.svg">
    {%css%}
  </head>
  <body>
    {%app_entry%}
    <footer>
      {%config%}
      {%scripts%}
      {%renderer%}
    </footer>
  </body>
</html>"""


def _safe_next(raw: str | None) -> str:
    """Only allow same-site absolute paths as post-login targets."""
    if raw and raw.startswith("/") and not raw.startswith("//"):
        return raw
    return "/app/"


def _content_security_policy() -> str:
    dash_app = current_app.config.get("DASH_APP")
    script_src = "'self' 'unsafe-inline'"
    if dash_app is not None:
        try:
            hashes = dash_app.csp_hashes()
        except Exception:  # noqa: BLE001 - CSP generation must never break a response
            logger.warning("datacheck: could not compute CSP hashes", exc_info=True)
            hashes = []
        if hashes:
            script_src = "'self' " + " ".join(hashes)
    return "; ".join(
        [
            "default-src 'self'",
            f"script-src {script_src}",
            "style-src 'self' 'unsafe-inline'",
            "img-src 'self' data:",
            "font-src 'self'",
            "connect-src 'self'",
            "form-action 'self'",
            "frame-ancestors 'none'",
            "base-uri 'self'",
        ]
    )


def _register_pages(app: Flask) -> None:
    @app.get("/health")
    def health():
        return {"status": "ok", "app": "Datacheck Quality Monitor"}

    @app.get("/login")
    def login_page():
        next_url = _safe_next(request.args.get("next"))
        if service.session_user(request.cookies.get(SESSION_COOKIE_NAME)):
            return redirect(next_url)
        return render_template(
            "login.html",
            next_url=next_url,
            demo_email=DEMO_USER_EMAIL,
            demo_password=DEMO_USER_PASSWORD,
        )

    @app.post("/signout")
    def signout():
        service.sign_out(request.cookies.get(SESSION_COOKIE_NAME, ""))
        response = redirect("/login")
        response.delete_cookie(SESSION_COOKIE_NAME, path="/")
        return response


def _register_headers(app: Flask) -> None:
    @app.after_request
    def _security_headers(response):
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Content-Security-Policy"] = _content_security_policy()
        if request.path.startswith("/api/"):
            response.headers["Cache-Control"] = "no-store"
        return response


def create_flask_app() -> Flask:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s %(message)s")
    app = Flask(
        __name__,
        static_folder=str(STATIC_DIR),
        static_url_path="/static",
        template_folder=str(TEMPLATE_DIR),
    )
    app.secret_key = SESSION_SECRET
    app.config.update(
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
        SESSION_COOKIE_SECURE=False,  # plain-http preview/dev; set TLS before flipping this
        JSON_SORT_KEYS=False,
    )

    db.init_db()
    ensure_seeded()

    register_api(app)
    _register_pages(app)
    guard.install_guards(app)
    _register_headers(app)
    return app


def configure_dash_app(dash_app) -> None:
    """Attach the layout and every callback to an already-constructed Dash app."""
    from .dash_app import callbacks_actions, callbacks_data, callbacks_state
    from .dash_app.layout import build_layout

    dash_app.title = "Datacheck Quality Monitor"
    dash_app.update_title = None
    dash_app.index_string = INDEX_TEMPLATE
    # A callable layout is served per request, which is how a refresh or a deep
    # link restores ?dataset=/?tab= without a URL -> component callback.
    dash_app.layout = build_layout

    callbacks_state.register()
    callbacks_data.register()
    callbacks_actions.register()
