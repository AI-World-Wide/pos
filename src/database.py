# -*- coding: utf-8 -*-
"""SQLAlchemy engine + session factory + init_db().

SQLite-only. No PostgreSQL connections — the production Dell has another POS
on its own PostgreSQL install that must not be touched.
"""
from __future__ import annotations

import configparser
import sys
from pathlib import Path

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import sessionmaker, Session

# When frozen (PyInstaller), data/ lives next to the .exe, not inside _MEIPASS.
if getattr(sys, "frozen", False):
    RUNTIME_DIR = Path(sys.executable).resolve().parent
    BUNDLE_DIR = Path(sys._MEIPASS)
else:
    RUNTIME_DIR = Path(__file__).resolve().parent.parent
    BUNDLE_DIR = RUNTIME_DIR

PROJECT_ROOT = RUNTIME_DIR
CONFIG_PATH = BUNDLE_DIR / "config.ini"
if (RUNTIME_DIR / "config.ini").exists():
    CONFIG_PATH = RUNTIME_DIR / "config.ini"


def _load_db_path() -> Path:
    config = configparser.ConfigParser()
    config.read(CONFIG_PATH, encoding="utf-8")
    rel = config.get("database", "path", fallback="data/pos.db")
    return RUNTIME_DIR / rel


DB_PATH = _load_db_path()
DB_PATH.parent.mkdir(parents=True, exist_ok=True)

# SQLite URL with relative path resolved to absolute for cross-platform safety.
engine: Engine = create_engine(
    f"sqlite:///{DB_PATH.as_posix()}",
    future=True,
    echo=False,
    connect_args={"check_same_thread": False},
)


# Enable foreign keys on every SQLite connection (off by default in SQLite).
@event.listens_for(engine, "connect")
def _enable_sqlite_fk(dbapi_conn, connection_record):
    cursor = dbapi_conn.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.close()


SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


def get_session() -> Session:
    """Open a new session. Caller is responsible for closing/committing."""
    return SessionLocal()


def init_db() -> None:
    """Create all tables if they don't exist, then seed users + permissions + areas."""
    from src.models import Base
    from src.seed_users import seed_users_and_permissions
    from src.seed_tables import seed_areas_and_tables

    Base.metadata.create_all(bind=engine)
    with SessionLocal() as session:
        seed_users_and_permissions(session)
        seed_areas_and_tables(session)
        session.commit()
