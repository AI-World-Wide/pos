# -*- coding: utf-8 -*-
"""Cafe POS — Flask entry point.

Serves the full POS application: cashier screen, back office, reports, settings.
Database: SQLite only (data/pos.db). No PostgreSQL connections.
"""
from __future__ import annotations

import configparser
import logging
from pathlib import Path

from flask import Flask, redirect, session, url_for

from src.database import init_db
from src.routes.auth import bp as auth_bp
from src.routes.backoffice import bp as backoffice_bp
from src.routes.cashier import bp as cashier_bp
from src.routes.reports import bp as reports_bp
from src.routes.settings import bp as settings_bp
from src.translations.ar import T

PROJECT_ROOT = Path(__file__).resolve().parent
CONFIG_PATH = PROJECT_ROOT / "config.ini"

# Configure logging to file
log_path = PROJECT_ROOT / "data" / "error.log"
log_path.parent.mkdir(parents=True, exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.FileHandler(str(log_path), encoding="utf-8"),
        logging.StreamHandler(),
    ],
)


def create_app() -> Flask:
    config = configparser.ConfigParser()
    config.read(CONFIG_PATH, encoding="utf-8")

    app = Flask(
        __name__,
        template_folder=str(PROJECT_ROOT / "templates"),
        static_folder=str(PROJECT_ROOT / "static"),
    )
    app.config["SECRET_KEY"] = config.get("app", "secret_key", fallback="dev-secret-change-me")

    # Make Arabic strings available in every template as `t.<key>`.
    class _T:
        def __getattr__(self, key):
            return T.get(key, f"<missing:{key}>")
        def __getitem__(self, key):
            return T.get(key, f"<missing:{key}>")

    @app.context_processor
    def _inject_translations():
        return {"t": _T()}

    # Register blueprints
    app.register_blueprint(auth_bp)
    app.register_blueprint(cashier_bp)
    app.register_blueprint(backoffice_bp)
    app.register_blueprint(reports_bp)
    app.register_blueprint(settings_bp)

    # Login guard: redirect to login if not authenticated
    @app.before_request
    def _require_login():
        from flask import request as req
        # Allow login page and static files
        if req.endpoint and (
            req.endpoint.startswith("auth.")
            or req.endpoint == "static"
        ):
            return None
        if not session.get("username"):
            return redirect(url_for("auth.login_page"))

    return app


app = create_app()


if __name__ == "__main__":
    config = configparser.ConfigParser()
    config.read(CONFIG_PATH, encoding="utf-8")

    init_db()  # idempotent: creates tables + seeds users on first run

    # Start print retry background thread
    try:
        from src.printer import _start_retry_loop
        _start_retry_loop()
    except Exception:
        pass

    app.run(
        host=config.get("app", "host", fallback="127.0.0.1"),
        port=config.getint("app", "port", fallback=5000),
        debug=config.getboolean("app", "debug", fallback=True),
    )
