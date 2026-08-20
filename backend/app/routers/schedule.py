"""
POST /api/schedule — Main scheduling endpoint (P3-T6).

Accepts a session_id + exam period configuration.
Pipeline:
  1. Load session (upload must have already happened via POST /api/upload)
  2. Reject if any Critical validation errors remain
  3. Build conflict graph
  4. Compute available dates from the period config
  5. Run CP-SAT solver
  6. On OPTIMAL/FEASIBLE → return full schedule
  7. On INFEASIBLE      → return infeasibility diagnostic data (FR-5 stub;
                           full diagnostics fleshed out in Phase 6)

The solver result is stored in the session for export use (Phase 5).
"""
from __future__ import annotations

from datetime import date
from typing import Optional

from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel, field_validator, model_validator

from app.conflict_graph import build_graph, graph_statistics, max_clique_size
from app.course_reference import fetch_all_mappings, update_display_name, upsert_course_map
from app.date_utils import available_dates
from app.scheduler import solve, verify_solution
from app.session_store import Session, get_session

router = APIRouter(prefix="/api", tags=["schedule"])


# ─────────────────────────────────────────────────────────────────────────────
# Request / response models
# ─────────────────────────────────────────────────────────────────────────────

class ScheduleRequest(BaseModel):
    session_id: str
    start_date: date
    end_date: date
    excluded_weekdays: list[int] = [4, 5]        # Fri + Sat by default
    excluded_dates: list[date] = []              # ad-hoc holidays
    timeout_seconds: float = 30.0

    @field_validator("excluded_weekdays")
    @classmethod
    def valid_weekdays(cls, v: list[int]) -> list[int]:
        if any(d < 0 or d > 6 for d in v):
            raise ValueError("excluded_weekdays must be integers 0–6 (Mon=0 … Sun=6)")
        return v

    @model_validator(mode="after")
    def start_before_end(self) -> "ScheduleRequest":
        if self.start_date > self.end_date:
            raise ValueError("start_date must be on or before end_date")
        return self


# ─────────────────────────────────────────────────────────────────────────────
# Endpoint
# ─────────────────────────────────────────────────────────────────────────────

@router.post("/schedule")
async def schedule(body: ScheduleRequest):
    """
    Run the CP-SAT scheduler for the given session and exam period.

    Success response shape:
    {
      status:           "OPTIMAL" | "FEASIBLE",
      session_id:       str,
      days_used:        int,
      total_courses:    int,
      max_load:         int,
      avg_courses_per_day: float,
      wall_time_seconds: float,
      schedule: {
        "YYYY-MM-DD": [
          { course_id, display_names: {dept: name}, student_count },
          ...
        ],
        ...
      }
    }

    Infeasibility response shape:
    {
      status:               "INFEASIBLE",
      session_id:           str,
      available_days:       int,
      min_days_required:    int,     ← max clique size (FR-5)
      additional_days_needed: int,
      wall_time_seconds:    float,
      top_students:         [...],   ← Phase 6 fleshed out
      bottleneck_courses:   [...]
    }
    """
    # ── 1. Load session ──────────────────────────────────────────────────────
    session = get_session(body.session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="الجلسة غير موجودة أو انتهت صلاحيتها.")

    # ── 2. Block if critical errors remain ───────────────────────────────────
    if session.validation_report and not session.validation_report.get("is_valid", True):
        n_errors = len(session.validation_report.get("errors", []))
        raise HTTPException(
            status_code=422,
            detail=f"لا يمكن تشغيل المجدول — يوجد {n_errors} خطأ حرج يجب حله أولاً.",
        )

    # ── 3. Build conflict graph ──────────────────────────────────────────────
    graph = build_graph(session.df)
    stats = graph_statistics(graph)

    # ── 4. Compute available dates ───────────────────────────────────────────
    days = available_dates(
        start=body.start_date,
        end=body.end_date,
        excluded_weekdays=body.excluded_weekdays,
        excluded_dates=body.excluded_dates,
    )

    if not days:
        raise HTTPException(
            status_code=422,
            detail="لا توجد أيام متاحة للامتحانات في الفترة المحددة — تحقق من إعدادات الفترة.",
        )

    # ── 5. Run CP-SAT ────────────────────────────────────────────────────────
    result = solve(
        graph,
        days,
        timeout_seconds=body.timeout_seconds,
        use_dsatur_hint=True,
    )

    # ── 6a. SUCCESS ──────────────────────────────────────────────────────────
    if result.status in ("OPTIMAL", "FEASIBLE"):
        # Build the rich schedule dict: date → list of course detail objects
        schedule_dict: dict[str, list[dict]] = {}
        for iso_date, course_ids in sorted(result.courses_per_day.items()):
            day_courses = []
            for cid in sorted(course_ids):
                info = graph.course_map.get(cid)
                # Find a representative academic level for the UI card summary
                # Since variants is dept -> set((level, name)), we flatten the levels
                level = ""
                if info:
                    all_levels = []
                    for vs in info.variants.values():
                        all_levels.extend(v[0] for v in vs if v[0])
                    if all_levels:
                        from collections import Counter
                        level = Counter(all_levels).most_common(1)[0][0]

                # Convert sets to lists of dicts for JSON serialization
                variants_list = {dept: [{"academic_level": v[0], "display_name": v[1]} for v in vs] for dept, vs in info.variants.items()} if info else {}

                day_courses.append({
                    "course_id": cid,
                    "variants": variants_list,
                    "student_count": len(info.students) if info else 0,
                    "academic_level": level,
                })
            schedule_dict[iso_date] = day_courses

        # Store result in session for export endpoints (Phase 5)
        session.validation_report["last_schedule"] = {
            "result": result,
            "graph": graph,
            "schedule_dict": schedule_dict,
        }

        # P7-T2: persist course-name map to SQLite (survives server restart)
        upsert_course_map(graph)

        total_courses = len(graph.nodes)
        avg_cpd = round(total_courses / result.days_used, 2) if result.days_used else 0

        return JSONResponse({
            "status": result.status,
            "session_id": body.session_id,
            "days_used": result.days_used,
            "total_courses": total_courses,
            "max_load": result.max_load,
            "avg_courses_per_day": avg_cpd,
            "wall_time_seconds": round(result.wall_time_seconds, 3),
            "schedule": schedule_dict,
        })

    # ── 6b. INFEASIBLE — spec §7.4: NEVER return a partial schedule ──────────
    clique_sz = max_clique_size(graph)
    additional_needed = max(0, clique_sz - len(days))

    # Top students by course count (Phase 6 will expand this)
    student_courses: dict[str, set[str]] = {}
    for cid, info in graph.course_map.items():
        for student in info.students:
            student_courses.setdefault(student, set()).add(cid)
    top_students = sorted(
        [{"name": s, "course_count": len(cs), "courses": sorted(cs)}
         for s, cs in student_courses.items()],
        key=lambda x: -x["course_count"],
    )[:10]

    # Top bottleneck courses by degree
    degree_map = stats["degree_map"]
    bottleneck = sorted(
        [{"course_id": cid, "degree": deg,
          "variants": {dept: [{"academic_level": v[0], "display_name": v[1]} for v in vs] for dept, vs in graph.course_map[cid].variants.items()}}
         for cid, deg in degree_map.items()],
        key=lambda x: -x["degree"],
    )[:10]

    return JSONResponse(
        status_code=200,   # not 4xx — the solver ran successfully; the data is infeasible
        content={
            "status": "INFEASIBLE",
            "session_id": body.session_id,
            "available_days": len(days),
            "min_days_required": clique_sz,
            "additional_days_needed": additional_needed,
            "wall_time_seconds": round(result.wall_time_seconds, 3),
            "top_students": top_students,
            "bottleneck_courses": bottleneck,
            "suggestions": _build_suggestions(clique_sz, len(days), top_students),
        },
    )


def _build_suggestions(
    min_days: int,
    available: int,
    top_students: list[dict],
) -> list[dict]:
    """Generate numbered, concrete suggestions (FR-5)."""
    suggestions = []
    n = 1

    if min_days > available:
        extra = min_days - available
        suggestions.append({
            "id": n,
            "action": "extend_period",
            "message": (
                f"أضف {extra} يوم{'ًا' if extra > 1 else ''} على الأقل إلى فترة الامتحانات. "
                f"الحد الأدنى المطلوب رياضياً هو {min_days} يوماً؛ "
                f"الأيام المتاحة حالياً: {available}."
            ),
            "link_to": "settings",
        })
        n += 1

    if top_students:
        busiest = top_students[0]
        suggestions.append({
            "id": n,
            "action": "review_student",
            "message": (
                f"راجع بيانات الطالب '{busiest['name']}' المسجّل في "
                f"{busiest['course_count']} مواد — يُعدّ من أكثر العوامل تأثيراً "
                f"في تعقيد الجدولة."
            ),
            "link_to": "validation",
        })
        n += 1

    return suggestions
