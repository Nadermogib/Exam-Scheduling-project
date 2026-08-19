"""
Upload, validation, session-patch, and template endpoints.

POST  /api/upload                         — P1-T1, P1-T8
GET   /api/template                       — P1-T9
PATCH /api/session/{id}/row/{row}/field/{field} — P4-T5 (inline cell correction)
"""
from __future__ import annotations

import io
from typing import Annotated

import pandas as pd
from fastapi import APIRouter, File, HTTPException, Path, UploadFile
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel

from app.ingestion import ARABIC_COLS, REQUIRED_ARABIC, IngestionError, read_excel
from app.session_store import create_session, get_session, update_session_df
from app.validation import COLUMN_LABELS, validate

router = APIRouter(prefix="/api", tags=["upload"])

# ─── constants ───────────────────────────────────────────────────────────────
MAX_UPLOAD_BYTES = 20 * 1024 * 1024  # 20 MB (P7-T8)
PATCHABLE_FIELDS = {"student_name", "department", "course_id", "course_display_name", "academic_level"}


# ─────────────────────────────────────────────────────────────────────────────
# POST /api/upload
# ─────────────────────────────────────────────────────────────────────────────

@router.post("/upload")
async def upload_file(file: Annotated[UploadFile, File()]):
    """
    Accept a .xlsx upload, parse it, run validation, and return the report.

    Response shape:
      {
        session_id: str,
        errors: [...],
        warnings: [...],
        row_count: int,
        is_valid: bool,
        rows: [...]   ← parsed rows as JSON (for the frontend data table)
      }
    """
    # ── File type guard ──────────────────────────────────────────────────────
    if not (file.filename or "").lower().endswith(".xlsx"):
        raise HTTPException(
            status_code=415,
            detail="نوع الملف غير مدعوم. يُرجى رفع ملف بصيغة .xlsx فقط.",
        )

    # ── Size guard ───────────────────────────────────────────────────────────
    file_bytes = await file.read()
    if len(file_bytes) > MAX_UPLOAD_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"حجم الملف يتجاوز الحد المسموح به ({MAX_UPLOAD_BYTES // (1024*1024)} ميغابايت).",
        )

    if len(file_bytes) == 0:
        raise HTTPException(status_code=400, detail="الملف فارغ.")

    # ── Parse ────────────────────────────────────────────────────────────────
    try:
        df = read_excel(file_bytes)
    except IngestionError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    # ── Session ──────────────────────────────────────────────────────────────
    session = create_session(df)

    # ── Validate ─────────────────────────────────────────────────────────────
    report = validate(df)
    session.validation_report = report

    # ── Serialise rows for the frontend data table ───────────────────────────
    rows = _df_to_rows(df)

    return JSONResponse({
        "session_id": session.session_id,
        **report,
        "rows": rows,
    })


# ─────────────────────────────────────────────────────────────────────────────
# PATCH /api/session/{session_id}/row/{row}/field/{field}
# Inline cell correction (P4-T5 / AQ-2 Option A)
# ─────────────────────────────────────────────────────────────────────────────

class PatchBody(BaseModel):
    value: str


@router.patch("/session/{session_id}/row/{row}/field/{field}")
async def patch_cell(
    session_id: Annotated[str, Path()],
    row: Annotated[int, Path(ge=2)],    # 1-based; row 1 is the header
    field: Annotated[str, Path()],
    body: PatchBody,
):
    """
    Update a single cell in the in-memory session DataFrame and re-run
    validation. Returns the updated validation report.

    *row* is the 1-based Excel row number (data starts at row 2).
    *field* is the internal column name (e.g. course_id, student_name).
    """
    if field not in PATCHABLE_FIELDS:
        raise HTTPException(
            status_code=400,
            detail=f"الحقل '{field}' غير قابل للتعديل. الحقول المتاحة: {', '.join(sorted(PATCHABLE_FIELDS))}",
        )

    session = get_session(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="الجلسة غير موجودة أو انتهت صلاحيتها.")

    if row not in session.df.index:
        raise HTTPException(
            status_code=404,
            detail=f"الصف {row} غير موجود في البيانات (الصفوف المتاحة: {session.df.index.min()}–{session.df.index.max()}).",
        )

    # Apply the edit
    session.df.at[row, field] = body.value.strip()
    update_session_df(session.session_id, session.df)

    # Re-run validation on the updated DataFrame
    report = validate(session.df)
    session.validation_report = report

    return JSONResponse({
        "session_id": session_id,
        **report,
        "rows": _df_to_rows(session.df),
        "patched": {"row": row, "field": field, "new_value": body.value.strip()},
    })


# ─────────────────────────────────────────────────────────────────────────────
# GET /api/template
# ─────────────────────────────────────────────────────────────────────────────

_EXAMPLE_ROWS = [
    ("أحمد محمد علي",    "شبكات الحاسوب",  "C0101", "أمن الشبكات",       "السنة الثالثة"),
    ("فاطمة يوسف حسن",  "اتصالات",         "C0201", "معالجة الإشارات",   "السنة الرابعة"),
    ("فاطمة يوسف حسن",  "اتصالات",         "C0202", "أنظمة الاتصالات",   "السنة الرابعة"),
]


@router.get("/template")
async def download_template():
    """
    Generate and return a downloadable .xlsx template file with the correct
    5 Arabic column headers and 3 example rows (P1-T9).
    """
    df_tmpl = pd.DataFrame(_EXAMPLE_ROWS, columns=REQUIRED_ARABIC)

    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as writer:
        df_tmpl.to_excel(writer, index=False, sheet_name="تسجيل الطلاب")
        ws = writer.sheets["تسجيل الطلاب"]
        ws.sheet_view.rightToLeft = True
        col_widths = [30, 22, 12, 40, 18]
        for i, width in enumerate(col_widths, start=1):
            ws.column_dimensions[ws.cell(row=1, column=i).column_letter].width = width

    buf.seek(0)
    return StreamingResponse(
        buf,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": 'attachment; filename="exam_schedule_template.xlsx"'},
    )


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _df_to_rows(df: pd.DataFrame) -> list[dict]:
    """Serialise the DataFrame to a list of row dicts with the Excel row number."""
    records = []
    for idx, row in df.iterrows():
        records.append({
            "row": int(idx),
            "student_name": row["student_name"],
            "department": row["department"],
            "course_id": row["course_id"],
            "course_display_name": row["course_display_name"],
            "academic_level": row["academic_level"],
        })
    return records
