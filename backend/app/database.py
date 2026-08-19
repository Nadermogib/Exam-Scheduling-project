"""
SQLite database initialisation and connection helper.

Schema
------
course_name_map
  course_id    TEXT   — unified course code (§5, §6)
  department   TEXT   — Arabic department name
  display_name TEXT   — department-specific course display name (المقرر)
  last_updated TEXT   — ISO-8601 timestamp of last upsert
  PRIMARY KEY (course_id, department)

This is the sole persistent store for the course-code reference (AQ-3 / P0-T7).
All other data (uploaded files, sessions, solver results) is in-memory only.
"""
from __future__ import annotations

import os
import sqlite3
from pathlib import Path

# The data directory sits alongside this file's package; configurable via env.
_DATA_DIR = Path(os.getenv("DB_DIR", Path(__file__).parent.parent / "data"))
DB_PATH = _DATA_DIR / "exam_scheduling.sqlite"


def get_connection() -> sqlite3.Connection:
    """Return a new SQLite connection with WAL mode enabled."""
    _DATA_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA foreign_keys=ON;")
    return conn


def init_db() -> None:
    """Create tables if they do not already exist (idempotent)."""
    with get_connection() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS course_name_map (
                course_id    TEXT NOT NULL,
                department   TEXT NOT NULL,
                display_name TEXT NOT NULL,
                last_updated TEXT NOT NULL,
                PRIMARY KEY (course_id, department)
            );
            """
        )
        conn.commit()
