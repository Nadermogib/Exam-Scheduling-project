"""
Course-Code Reference endpoints (P7-T2, P7-T3).

GET  /api/reference                    — read all persisted course↔dept↔name mappings
PATCH /api/reference/{course_id}/{dept} — update a display name (editable reference screen)
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.course_reference import fetch_all_mappings, update_display_name

router = APIRouter(prefix="/api/reference", tags=["reference"])


class NameUpdateBody(BaseModel):
    display_name: str


@router.get("")
async def get_reference():
    """
    Return all persisted course ↔ department ↔ display_name rows.
    Reads from SQLite — survives server restarts (P7-T2, NFR Reusability).
    """
    rows = fetch_all_mappings()
    return {"count": len(rows), "mappings": rows}


@router.patch("/{course_id}/{department}")
async def patch_reference(course_id: str, department: str, body: NameUpdateBody):
    """
    Manually correct a display name for a given course_id / department pair (P7-T3).
    Returns 404 if the mapping does not exist yet (must solve first to populate it).
    """
    if not body.display_name.strip():
        raise HTTPException(status_code=422, detail="display_name لا يمكن أن يكون فارغاً.")
    updated = update_display_name(course_id, department, body.display_name.strip())
    if not updated:
        raise HTTPException(
            status_code=404,
            detail=f"لم يُعثر على السجل: course_id='{course_id}', department='{department}'. "
                   f"يُرجى تشغيل الجدولة أولاً.",
        )
    return {"course_id": course_id, "department": department, "display_name": body.display_name.strip()}
