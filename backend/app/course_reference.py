"""
SQLite-backed course-code reference persistence (P7-T2).

After every successful solve, upsert the full course_id ↔ department ↔
display_name mapping into the `course_name_map` table so it survives server
restarts.  The Course-Code Reference API reads from this table, not from any
in-memory session, satisfying the NFR Reusability requirement.
"""
from __future__ import annotations

from datetime import datetime, timezone

from app.conflict_graph import ConflictGraph
from app.database import get_connection


def upsert_course_map(graph: ConflictGraph) -> int:
    """
    Upsert all course ↔ department ↔ display_name rows from a solved graph.

    Returns the number of rows upserted.
    """
    now = datetime.now(timezone.utc).isoformat()
    rows: list[tuple[str, str, str, str, str]] = []

    for cid, info in graph.course_map.items():
        for dept, variants in info.variants.items():
            for level, name in variants:
                rows.append((cid, dept, level, name, now))

    if not rows:
        return 0

    with get_connection() as conn:
        conn.executemany(
            """
            INSERT INTO course_name_map (course_id, department, academic_level, display_name, last_updated)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(course_id, department, academic_level)
            DO UPDATE SET display_name = excluded.display_name,
                          last_updated = excluded.last_updated;
            """,
            rows,
        )
        conn.commit()

    return len(rows)


def fetch_all_mappings() -> list[dict]:
    """
    Fetch the complete course-code reference table from SQLite.
    Returns a list of dicts: {course_id, department, academic_level, display_name, last_updated}.
    """
    with get_connection() as conn:
        cur = conn.execute(
            """
            SELECT course_id, department, academic_level, display_name, last_updated
            FROM course_name_map
            ORDER BY course_id, department, academic_level;
            """
        )
        return [dict(row) for row in cur.fetchall()]


def update_display_name(course_id: str, department: str, new_name: str) -> bool:
    """
    Manually update a display name (P7-T3 — editable reference screen).
    Returns True if the row existed and was updated, False otherwise.
    """
    now = datetime.now(timezone.utc).isoformat()
    with get_connection() as conn:
        cur = conn.execute(
            """
            UPDATE course_name_map
            SET display_name = ?, last_updated = ?
            WHERE course_id = ? AND department = ?;
            """,
            (new_name, now, course_id, department),
        )
        conn.commit()
        return cur.rowcount > 0
