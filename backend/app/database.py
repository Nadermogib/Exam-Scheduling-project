"""
SQLite database initialisation and connection helper.

Schema
------
course_name_map
  course_id      TEXT   — unified course code (§5, §6)
  department     TEXT   — Arabic department name
  academic_level TEXT   — e.g., 'ف4'
  display_name   TEXT   — department-specific course display name (المقرر)
  last_updated   TEXT   — ISO-8601 timestamp of last upsert
  PRIMARY KEY (course_id, department, academic_level)

print_settings
  key   TEXT PRIMARY KEY  — setting key (e.g. 'header_text', 'logo_data_url')
  value TEXT              — setting value (plain text or base-64 data URL)

This is the sole persistent store for the course-code reference (AQ-3 / P0-T7)
and print settings (Phase 8-B).
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
        # Migration for multi-variant support (Phase 8 bugfix)
        try:
            conn.execute("SELECT academic_level FROM course_name_map LIMIT 1")
        except sqlite3.OperationalError:
            # If the column doesn't exist, this is an old schema. Drop and recreate.
            conn.execute("DROP TABLE IF EXISTS course_name_map;")

        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS course_name_map (
                course_id      TEXT NOT NULL,
                department     TEXT NOT NULL,
                academic_level TEXT NOT NULL,
                display_name   TEXT NOT NULL,
                last_updated   TEXT NOT NULL,
                PRIMARY KEY (course_id, department, academic_level)
            );
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS print_settings (
                key   TEXT NOT NULL PRIMARY KEY,
                value TEXT NOT NULL
            );
            """
        )
        conn.commit()
