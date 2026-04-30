"""DB connection, initialization, and migrations."""

import logging
import sqlite3
from pathlib import Path

from src.config import DB_PATH
from src.db.models import SCHEMA_SQL

logger = logging.getLogger(__name__)


def get_connection(db_path: Path | None = None) -> sqlite3.Connection:
    """Return a connection to the SQLite database, creating it if needed."""
    path = db_path or DB_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db(db_path: Path | None = None) -> None:
    """Create tables and indexes if they don't exist."""
    conn = get_connection(db_path)
    try:
        conn.executescript(SCHEMA_SQL)
        conn.commit()
        logger.info("Database initialized at %s", db_path or DB_PATH)
    finally:
        conn.close()
