# -*- coding: utf-8 -*-
"""Cafe POS — Flask entry point.

Phase 1: serves the Arabic placeholder page listing categories and items.
"""
from __future__ import annotations

import configparser
from pathlib import Path

from flask import Flask

from src.database import init_db
from src.routes.cashier import bp as cashier_bp
from src.translations.ar import T

PROJECT_ROOT = Path(__file__).resolve().parent
CONFIG_PATH = PROJECT_ROOT / "config.ini"


def create_app() -> Flask:
    config = configparser.ConfigParser()
    config.read(CONFIG_PATH, encoding="utf-8")

    app = Flask(
        __name__,
        template_folder=str(PROJECT_ROOT / "templates"),
        static_folder=str(PROJECT_ROOT / "static"),
    )
    app.config["SECRET_KEY"] = config.get("app", "secret_key", fallback="dev")

    # Make Arabic strings available in every template as `t.<key>`.
    class _T:
        def __getattr__(self, key):
            return T.get(key, f"<missing:{key}>")

    @app.context_processor
    def _inject_translations():
        return {"t": _T()}

    app.register_blueprint(cashier_bp)
    return app


app = create_app()


if __name__ == "__main__":
    config = configparser.ConfigParser()
    config.read(CONFIG_PATH, encoding="utf-8")

    init_db()  # idempotent: creates tables + seeds users on first run

    app.run(
        host=config.get("app", "host", fallback="127.0.0.1"),
        port=config.getint("app", "port", fallback=5000),
        debug=config.getboolean("app", "debug", fallback=True),
    )
