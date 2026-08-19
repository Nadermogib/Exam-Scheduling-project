"""
GET /api/db/status — confirms the SQLite database is reachable and returns
the current row count of course_name_map (P0-T7).
"""
from fastapi import APIRouter
from fastapi.responses import JSONResponse

from app.database import get_connection

router = APIRouter(prefix="/api", tags=["system"])


@router.get("/db/status")
async def db_status():
    """Smoke-test the SQLite connection and return the current mapping row count."""
    with get_connection() as conn:
        row = conn.execute("SELECT COUNT(*) AS cnt FROM course_name_map;").fetchone()
    return JSONResponse({"ok": True, "row_count": row["cnt"]})
