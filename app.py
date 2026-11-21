"""Datacheck Quality Monitor — application entrypoint.

Boots a single Flask process that serves the sign-in page, the JSON API and the
Dash workspace at /app/. Two documented ways to start it:

    python3 app.py            # http://0.0.0.0:8050  (Dash's conventional port)
    flask run                 # honours .flaskenv: http://0.0.0.0:5000

The database schema and the demo data are created on this path, so a fresh clone
with no .env renders a populated dashboard immediately.
"""

from __future__ import annotations

import os
from pathlib import Path

import dash

from datacheck.main import configure_dash_app, create_flask_app

BASE_DIR = Path(__file__).resolve().parent

# Exactly ONE Flask instance may be reachable at module level: `flask run` scans
# the module and refuses to choose when it finds several, so the Flask app is
# only ever exposed as `server` — the attribute Dash, gunicorn and `flask run`
# all expect. (Binding it to a second name such as `flask_app` breaks the
# clean-clone boot with "Detected multiple Flask applications in module 'app'".)
app = dash.Dash(
    __name__,
    server=create_flask_app(),
    url_base_pathname="/app/",
    assets_folder=str(BASE_DIR / "datacheck" / "static"),
    assets_ignore=r"login\.js",
    title="Datacheck Quality Monitor",
    update_title=None,
    suppress_callback_exceptions=False,
)
configure_dash_app(app)

# WSGI app for `flask run`, `gunicorn app:server` and every other WSGI server.
server = app.server
server.config["DASH_APP"] = app


if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=int(os.environ.get("PORT", 8050)),
        debug=False,
    )
