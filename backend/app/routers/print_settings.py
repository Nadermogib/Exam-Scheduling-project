"""
Print Settings router — Phase 8-B.

Provides GET and PATCH endpoints for persisting the print table header text
and the university logo (stored as a base-64 data URL) in the SQLite
print_settings table.

Endpoints
---------
GET  /api/print-settings       → { header_text: str, logo_data_url: str | None, university_text: str | None }
PATCH /api/print-settings      → accepts { header_text?, logo_data_url?, university_text? }, upserts, returns updated settings
DELETE /api/print-settings/logo → removes the custom logo, falls back to default
"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from app.database import get_connection

router = APIRouter(prefix="/api", tags=["print-settings"])

# ── Allowed setting keys ─────────────────────────────────────────────────────
_ALLOWED_KEYS = {"header_text", "logo_data_url", "university_text"}


# ── Helpers ──────────────────────────────────────────────────────────────────

def _get_all() -> dict[str, str | None]:
    """Fetch all print settings from SQLite. Missing keys return None."""
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT key, value FROM print_settings WHERE key IN ('header_text', 'logo_data_url', 'university_text')"
        ).fetchall()
    result: dict[str, str | None] = {k: None for k in _ALLOWED_KEYS}
    for row in rows:
        result[row["key"]] = row["value"]
    return result


def _upsert(key: str, value: str) -> None:
    """Insert or replace a single setting."""
    with get_connection() as conn:
        conn.execute(
            "INSERT INTO print_settings (key, value) VALUES (?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
            (key, value),
        )
        conn.commit()


def _delete(key: str) -> None:
    """Delete a setting key (resets to default)."""
    with get_connection() as conn:
        conn.execute("DELETE FROM print_settings WHERE key = ?", (key,))
        conn.commit()


# ── Request model ─────────────────────────────────────────────────────────────

class PrintSettingsPatch(BaseModel):
    header_text: Optional[str] = None
    logo_data_url: Optional[str] = None
    university_text: Optional[str] = None


# ── Routes ────────────────────────────────────────────────────────────────────

@router.get("/print-settings")
async def get_print_settings():
    """
    Return current print settings.

    Returns header_text, logo_data_url, and university_text.
    Fields may be None if the user has not set them yet (frontend uses defaults).
    """
    settings = _get_all()
    return JSONResponse(settings)


@router.patch("/print-settings")
async def patch_print_settings(body: PrintSettingsPatch):
    """
    Upsert one or both print settings.

    Only non-None fields in the request body are written. The other fields
    retain their current values.
    """
    if body.header_text is not None:
        _upsert("header_text", body.header_text)
    if body.logo_data_url is not None:
        _upsert("logo_data_url", body.logo_data_url)
    if body.university_text is not None:
        _upsert("university_text", body.university_text)

    return JSONResponse(_get_all())


@router.delete("/print-settings/logo")
async def delete_custom_logo():
    """
    Remove the custom logo, reverting to the default university logo asset.
    """
    _delete("logo_data_url")
    return JSONResponse({"detail": "تمت إزالة الشعار المخصص. سيُستخدم الشعار الافتراضي."})
