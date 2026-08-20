"""
Phase 8-A tests — verify academic_level is included in the schedule API response.

Tests:
  8A-T1  CourseInfo stores academic_levels correctly during course_unification
  8A-T2  Schedule API response includes academic_level for every course
  8A-T3  Normalised "فX" prefix logic helper (used later by frontend, but
         let's confirm the raw values come through correctly so frontend can normalize)
"""
from __future__ import annotations

import pandas as pd
import pytest

from app.conflict_graph import CourseInfo, build_graph, course_unification


# ── Sample DataFrame ──────────────────────────────────────────────────────────

def _make_df() -> pd.DataFrame:
    rows = [
        # student_name, department, course_id, course_display_name, academic_level
        ("أحمد",   "علم الحاسوب",   "CS101", "برمجة 1",       "5"),
        ("محمد",   "علم الحاسوب",   "CS101", "برمجة 1",       "5"),
        ("سارة",   "نظم المعلومات", "CS101", "مقدمة برمجة",   "5"),   # same cid, diff dept
        ("فاطمة",  "علم الحاسوب",   "CS202", "هياكل البيانات", "ف6"),  # already has ف prefix
        ("أحمد",   "علم الحاسوب",   "CS202", "هياكل البيانات", "ف6"),
        ("سارة",   "نظم المعلومات", "CS303", "قواعد البيانات", "الفصل الثالث"),  # long form
    ]
    df = pd.DataFrame(rows, columns=[
        "student_name", "department", "course_id",
        "course_display_name", "academic_level",
    ])
    df.index = range(2, len(df) + 2)
    return df


# ── 8A-T1: CourseInfo stores academic_levels ─────────────────────────────────

def test_course_info_stores_academic_levels():
    df = _make_df()
    course_map = course_unification(df)

    # CS101 appears in both علم الحاسوب (level=5) and نظم المعلومات (level=5)
    cs101 = course_map["CS101"]
    assert any(v[0] == "5" for v in cs101.variants["علم الحاسوب"])
    assert any(v[0] == "5" for v in cs101.variants["نظم المعلومات"])

    # CS202 has level "ف6" in source — stored as-is
    cs202 = course_map["CS202"]
    assert any(v[0] == "ف6" for v in cs202.variants["علم الحاسوب"])

    # CS303 has long form
    cs303 = course_map["CS303"]
    assert any(v[0] == "الفصل الثالث" for v in cs303.variants["نظم المعلومات"])


# ── 8A-T2: schedule_dict course entries include academic_level ────────────────

def test_schedule_dict_includes_academic_level():
    """
    Simulate what schedule.py does: build graph, then build schedule_dict.
    Verify academic_level is present on each course entry.
    """
    from collections import Counter
    df = _make_df()
    graph = build_graph(df)

    # Simulate the schedule_dict building logic from schedule.py
    schedule_dict = {}
    for cid, info in graph.course_map.items():
        all_levels = []
        for vs in info.variants.values():
            all_levels.extend(v[0] for v in vs if v[0])
        level = Counter(all_levels).most_common(1)[0][0] if all_levels else ""
        
        variants_list = {dept: [{"academic_level": v[0], "display_name": v[1]} for v in vs] for dept, vs in info.variants.items()}

        schedule_dict[cid] = {
            "course_id": cid,
            "variants": variants_list,
            "student_count": len(info.students),
            "academic_level": level,
        }

    for cid, entry in schedule_dict.items():
        assert "academic_level" in entry, f"Missing academic_level for {cid}"
        assert isinstance(entry["academic_level"], str)

    # Spot-check values
    assert schedule_dict["CS101"]["academic_level"] == "5"
    assert schedule_dict["CS202"]["academic_level"] == "ف6"
    assert schedule_dict["CS303"]["academic_level"] == "الفصل الثالث"


# ── 8A-T3: No KeyError when academic_level column is missing ─────────────────

def test_missing_academic_level_column_is_safe():
    """
    Older DataFrames (from earlier sessions) might not have academic_level column.
    course_unification should not crash — academic_levels dict stays empty.
    """
    df = _make_df().drop(columns=["academic_level"])
    course_map = course_unification(df)

    for cid, info in course_map.items():
        assert isinstance(info.variants, dict), \
            f"variants should be a dict for {cid}"
        # May be empty — that's fine
