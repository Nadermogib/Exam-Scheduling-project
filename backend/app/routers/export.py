"""
Excel export endpoints — Phase 5.

GET /api/export/master               → P5-T5 master schedule
GET /api/export/department/{name}    → P5-T6 per-department schedule
GET /api/export/infeasibility        → P6-T6 infeasibility report

Both endpoints read the last solved schedule from the session store.
Both files are RTL-formatted, one-sheet workbooks (except infeasibility which has 4 sheets).
"""
from __future__ import annotations

import io
from urllib.parse import quote

import pandas as pd
from fastapi import APIRouter, HTTPException, Path
from fastapi.responses import StreamingResponse
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

from app.session_store import get_session

router = APIRouter(prefix="/api/export", tags=["export"])

# ─── Colour palette ───────────────────────────────────────────────────────────
HEADER_FILL = PatternFill("solid", fgColor="1c2330")
HEADER_FONT = Font(bold=True, color="00b4d8", name="Cairo", size=11)
ACCENT_FILL = PatternFill("solid", fgColor="161b22")
DATE_FONT   = Font(bold=True, color="3fb950", name="Cairo", size=10)
BODY_FONT   = Font(color="e6edf3", name="Cairo", size=10)


def _style_ws(ws, headers: list[str], col_widths: list[int]) -> None:
    """Apply RTL, header styling, and column widths to a worksheet."""
    ws.sheet_view.rightToLeft = True
    for col_i, (header, width) in enumerate(zip(headers, col_widths), start=1):
        cell = ws.cell(row=1, column=col_i)
        cell.value = header
        cell.font  = HEADER_FONT
        cell.fill  = HEADER_FILL
        cell.alignment = Alignment(horizontal="right", vertical="center", wrap_text=True)
        ws.column_dimensions[get_column_letter(col_i)].width = width
    ws.row_dimensions[1].height = 22


def _stream(buf: io.BytesIO, filename: str) -> StreamingResponse:
    buf.seek(0)
    encoded = quote(filename)
    return StreamingResponse(
        buf,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={
            "Content-Disposition": f"attachment; filename*=UTF-8''{encoded}",
        },
    )


# ─────────────────────────────────────────────────────────────────────────────
# P5-T5 — Master schedule export
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/master")
async def export_master(session_id: str):
    """
    Download the complete schedule as an Excel file.

    Columns:
      التاريخ | رمز المادة | الأقسام والمسميات | عدد الطلاب

    One row per course. Cross-department name variants are listed together
    in the Departments column (one line per department).
    """
    session = _get_valid_session(session_id)
    last = session.validation_report.get("last_schedule")
    if not last:
        raise HTTPException(status_code=422, detail="لم يتم تشغيل الجدولة بعد لهذه الجلسة.")

    result  = last["result"]
    graph   = last["graph"]

    headers = ["التاريخ", "رمز المادة", "مسميات الأقسام", "عدد الطلاب"]
    widths  = [16, 14, 52, 14]

    rows: list[tuple] = []
    for iso_date, courses in sorted(last["schedule_dict"].items()):
        for c in courses:
            cid  = c["course_id"]
            info = graph.course_map.get(cid)
            names_str = "\n".join(f"{dept}: {name}" for dept, name in (info.dept_names.items() if info else {}.items()))
            students  = len(info.students) if info else 0
            rows.append((iso_date, cid, names_str, students))

    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as writer:
        df = pd.DataFrame(rows, columns=headers)
        df.to_excel(writer, index=False, sheet_name="الجدول الكامل")
        ws = writer.sheets["الجدول الكامل"]
        _style_ws(ws, headers, widths)

        # Style data rows
        for row_i, row_data in enumerate(rows, start=2):
            for col_i in range(1, len(headers) + 1):
                cell = ws.cell(row=row_i, column=col_i)
                cell.font = DATE_FONT if col_i == 1 else BODY_FONT
                cell.alignment = Alignment(horizontal="right", vertical="center", wrap_text=True)
                cell.fill = ACCENT_FILL if row_i % 2 == 0 else PatternFill()
            ws.row_dimensions[row_i].height = max(30, 15 * len(str(row_data[2]).split("\n")))

    return _stream(buf, "الجدول_الكامل.xlsx")


# ─────────────────────────────────────────────────────────────────────────────
# P5-T6 — Per-department schedule export
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/department/{dept_name}")
async def export_department(
    dept_name: str = Path(..., description="اسم القسم بالعربية"),
    session_id: str = "",
):
    """
    Download the schedule for a single department.

    Only courses that have an entry in this department's name mapping are
    included. Display names use ONLY that department's المقرر value —
    no cross-department name leakage. (Acceptance Criterion 5)

    Columns:
      التاريخ | رمز المادة | اسم المقرر | عدد الطلاب
    """
    session = _get_valid_session(session_id)
    last = session.validation_report.get("last_schedule")
    if not last:
        raise HTTPException(status_code=422, detail="لم يتم تشغيل الجدولة بعد لهذه الجلسة.")

    graph = last["graph"]

    headers = ["التاريخ", "رمز المادة", "اسم المقرر", "عدد الطلاب"]
    widths  = [16, 14, 46, 14]

    rows: list[tuple] = []
    for iso_date, courses in sorted(last["schedule_dict"].items()):
        for c in courses:
            cid  = c["course_id"]
            info = graph.course_map.get(cid)
            if not info or dept_name not in info.dept_names:
                continue        # skip courses not in this department
            dept_display_name = info.dept_names[dept_name]   # ONLY this dept's name
            students = len(info.students)
            rows.append((iso_date, cid, dept_display_name, students))

    if not rows:
        raise HTTPException(
            status_code=404,
            detail=f"القسم '{dept_name}' غير موجود في بيانات الجلسة أو ليس له مواد مجدولة.",
        )

    safe_name = dept_name.replace("/", "_").replace("\\", "_")
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as writer:
        df = pd.DataFrame(rows, columns=headers)
        df.to_excel(writer, index=False, sheet_name=f"جدول {safe_name[:25]}")
        ws = list(writer.sheets.values())[0]
        _style_ws(ws, headers, widths)
        for row_i, _ in enumerate(rows, start=2):
            for col_i in range(1, len(headers) + 1):
                cell = ws.cell(row=row_i, column=col_i)
                cell.font = DATE_FONT if col_i == 1 else BODY_FONT
                cell.alignment = Alignment(horizontal="right", vertical="center")
                cell.fill = ACCENT_FILL if row_i % 2 == 0 else PatternFill()

    return _stream(buf, f"جدول_{safe_name}.xlsx")


# ─── Helper ───────────────────────────────────────────────────────────────────

def _get_valid_session(session_id: str):
    if not session_id:
        raise HTTPException(status_code=400, detail="session_id مطلوب.")
    session = get_session(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="الجلسة غير موجودة أو انتهت صلاحيتها.")
    return session

# ─────────────────────────────────────────────────────────────────────────────
# P6-T6 — Infeasibility report export
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/infeasibility")
async def export_infeasibility(session_id: str):
    """
    Download the infeasibility report with four sheets:
    Summary, Top Students, Bottleneck Courses, Suggestions.
    """
    session = _get_valid_session(session_id)
    last = session.validation_report.get("last_schedule")
    if not last:
        raise HTTPException(status_code=422, detail="لم يتم تشغيل الجدولة بعد لهذه الجلسة.")

    result = last["result"]
    if getattr(result, "status", None) != "INFEASIBLE":
        raise HTTPException(status_code=400, detail="الجدول ليس في حالة غير ممكنة.")

    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as writer:
        # Sheet 1: Summary
        df_summary = pd.DataFrame([
            ("الأيام المتاحة", result.available_days),
            ("الحد الأدنى المطلوب", result.min_days_required),
            ("أيام إضافية مطلوبة", result.additional_days_needed),
        ], columns=["المقياس", "القيمة"])
        df_summary.to_excel(writer, index=False, sheet_name="الملخص")
        _style_ws(writer.sheets["الملخص"], ["المقياس", "القيمة"], [30, 20])

        # Sheet 2: Top Students
        if result.top_students:
            rows = [(s["name"], s["course_count"], " · ".join(s["courses"])) for s in result.top_students]
            df_students = pd.DataFrame(rows, columns=["اسم الطالب", "عدد المواد", "المواد"])
            df_students.to_excel(writer, index=False, sheet_name="الطلاب الأكثر تأثيرا")
            _style_ws(writer.sheets["الطلاب الأكثر تأثيرا"], ["اسم الطالب", "عدد المواد", "المواد"], [40, 15, 60])

        # Sheet 3: Bottleneck Courses
        if result.bottleneck_courses:
            rows = [
                (c["course_id"], c["degree"], " | ".join(f"{d}: {n}" for d, n in c["display_names"].items()))
                for c in result.bottleneck_courses
            ]
            df_courses = pd.DataFrame(rows, columns=["رمز المادة", "درجة التعارض", "الأقسام والمسميات"])
            df_courses.to_excel(writer, index=False, sheet_name="المواد الأكثر تعارضا")
            _style_ws(writer.sheets["المواد الأكثر تعارضا"], ["رمز المادة", "درجة التعارض", "الأقسام والمسميات"], [15, 15, 60])

        # Sheet 4: Suggestions
        if result.suggestions:
            rows = [(s["id"], s["action"], s["message"]) for s in result.suggestions]
            df_suggs = pd.DataFrame(rows, columns=["رقم", "الإجراء", "التفاصيل"])
            df_suggs.to_excel(writer, index=False, sheet_name="توصيات الحل")
            _style_ws(writer.sheets["توصيات الحل"], ["رقم", "الإجراء", "التفاصيل"], [10, 20, 80])

    return _stream(buf, "تقرير_عدم_إمكانية_الجدولة.xlsx")
