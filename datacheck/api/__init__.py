"""Register every JSON blueprint on the Flask app."""

from __future__ import annotations

from flask import Flask

from . import auth, datasets, rules, rules_write, runs
from .responses import register_error_handlers


def register_api(app: Flask) -> None:
    app.register_blueprint(auth.bp)
    app.register_blueprint(datasets.bp)
    app.register_blueprint(runs.bp)
    app.register_blueprint(rules.bp)
    app.register_blueprint(rules_write.bp)
    register_error_handlers(app)
