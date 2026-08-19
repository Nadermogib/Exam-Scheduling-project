"""
Unit tests for Phase 1: data ingestion and all 6 validation rules.

Tests operate on small in-memory DataFrames — no file I/O required.
Each rule has at least one "should flag" and one "should not flag" case.

Run with:
    pytest tests/ -v
"""
from __future__ import annotations

import io
from pathlib import Path

import pandas as pd
import pytest

# Allow running pytest from the backend/ directory
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.ingestion import read_excel, IngestionError, ARABIC_COLS, REQUIRED_ARABIC
from app.validation import validate

# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _make_df(rows: list[tuple]) -> pd.DataFrame:
    """Build a normalised DataFrame directly (bypasses file I/O)."""
    df = pd.DataFrame(rows, columns=[
        "student_name", "department", "course_id",
        "course_display_name", "academic_level"
    ])
    df.index = range(2, len(df) + 2)   # 1-based, data from row 2
    for col in df.columns:
        df[col] = df[col].fillna("").astype(str).str.strip()
    return df


def _errors(report: dict) -> list[dict]:
    return report["errors"]


def _warnings(report: dict) -> list[dict]:
    return report["warnings"]


# ─────────────────────────────────────────────────────────────────────────────
# Ingestion tests (P1-T1)
# ─────────────────────────────────────────────────────────────────────────────

class TestIngestion:
    def test_read_valid_fixture(self):
        """The real test_fixture.xlsx parses without error."""
        fixture_path = Path(__file__).parent.parent.parent / "fixtures" / "test_fixture.xlsx"
        if not fixture_path.exists():
            pytest.skip("test_fixture.xlsx not yet generated")
        df = read_excel(fixture_path.read_bytes())
        assert list(df.columns) == [
            "student_name", "department", "course_id",
            "course_display_name", "academic_level"
        ]
        assert len(df) > 0
        # Row index should start at 2 (header is row 1)
        assert df.index[0] == 2

    def test_raises_on_empty_file(self, tmp_path):
        """Zero-byte file raises IngestionError."""
        with pytest.raises(IngestionError):
            read_excel(b"")

    def test_raises_on_wrong_format(self):
        """Non-Excel bytes raise IngestionError."""
        with pytest.raises(IngestionError):
            read_excel(b"this is not an xlsx file")

    def test_raises_on_missing_columns(self, tmp_path):
        """File missing required Arabic columns raises IngestionError."""
        buf = io.BytesIO()
        pd.DataFrame({"ColA": [1], "ColB": [2]}).to_excel(buf, index=False)
        buf.seek(0)
        with pytest.raises(IngestionError, match="مفقودة"):
            read_excel(buf.read())

    def test_whitespace_stripped(self, tmp_path):
        """Leading/trailing whitespace in cells is stripped."""
        buf = io.BytesIO()
        row = {"اسم الطالب": "  أحمد  ", "القسم": " شبكات ", "رمز المادة": " C01 ",
               "المقرر": "  مادة  ", "الفصل": "  ث3  "}
        pd.DataFrame([row]).to_excel(buf, index=False)
        buf.seek(0)
        df = read_excel(buf.read())
        assert df.iloc[0]["student_name"] == "أحمد"
        assert df.iloc[0]["course_id"] == "C01"


# ─────────────────────────────────────────────────────────────────────────────
# Rule 1 — blank required cells (P1-T2)
# ─────────────────────────────────────────────────────────────────────────────

class TestRule1:
    def test_flags_blank_department(self):
        df = _make_df([("أحمد", "", "C01", "مادة", "ث3")])
        report = validate(df)
        flagged = [e for e in _errors(report) if e["rule"] == 1 and e["column"] == "department"]
        assert len(flagged) == 1
        assert flagged[0]["severity"] == "critical"
        assert flagged[0]["row"] == 2

    def test_flags_blank_student_name(self):
        df = _make_df([("", "قسم", "C01", "مادة", "ث3")])
        report = validate(df)
        flagged = [e for e in _errors(report) if e["rule"] == 1 and e["column"] == "student_name"]
        assert len(flagged) == 1

    def test_flags_blank_display_name(self):
        df = _make_df([("أحمد", "قسم", "C01", "", "ث3")])
        report = validate(df)
        flagged = [e for e in _errors(report) if e["rule"] == 1 and e["column"] == "course_display_name"]
        assert len(flagged) == 1

    def test_clean_row_produces_no_rule1_errors(self):
        df = _make_df([("أحمد", "قسم", "C01", "مادة", "ث3")])
        report = validate(df)
        r1 = [e for e in _errors(report) if e["rule"] == 1]
        assert len(r1) == 0


# ─────────────────────────────────────────────────────────────────────────────
# Rule 2 — blank course_id (P1-T3)
# ─────────────────────────────────────────────────────────────────────────────

class TestRule2:
    def test_blank_course_id_surfaces_rule2(self):
        df = _make_df([("أحمد", "قسم", "", "مادة", "ث3")])
        report = validate(df)
        r2 = [e for e in _errors(report) if e["rule"] == 2]
        assert len(r2) == 1
        assert r2[0]["severity"] == "critical"
        assert "course_id" in r2[0]["message"] or "رمز المادة" in r2[0]["message"]

    def test_blank_course_id_rule1_deduplicated(self):
        """Rule 1 should NOT also fire for course_id when Rule 2 already covers it."""
        df = _make_df([("أحمد", "قسم", "", "مادة", "ث3")])
        report = validate(df)
        r1_for_course_id = [
            e for e in _errors(report)
            if e["rule"] == 1 and e["column"] == "course_id"
        ]
        assert len(r1_for_course_id) == 0

    def test_non_blank_course_id_produces_no_rule2(self):
        df = _make_df([("أحمد", "قسم", "C01", "مادة", "ث3")])
        report = validate(df)
        assert len([e for e in _errors(report) if e["rule"] == 2]) == 0


# ─────────────────────────────────────────────────────────────────────────────
# Rule 3 — same course_id + same dept, two display names (P1-T4)
# ─────────────────────────────────────────────────────────────────────────────

class TestRule3:
    def test_flags_real_world_example(self):
        """C0508 in شبكات الحاسوب with two names → Critical."""
        df = _make_df([
            ("وليد",  "شبكات الحاسوب", "C0508", "الشبكات اللاسلكية والموبايل",       "ث4"),
            ("وليد",  "شبكات الحاسوب", "C0508", "شبكات لاسلكية والاتصالات الخلوية",  "ث4"),
        ])
        report = validate(df)
        r3 = [e for e in _errors(report) if e["rule"] == 3]
        assert len(r3) == 1
        assert r3[0]["severity"] == "critical"
        assert len(r3[0]["extra"]["conflicting_names"]) == 2
        assert "C0508" in r3[0]["extra"]["course_id"]

    def test_same_course_id_same_name_no_error(self):
        """Same course_id + same dept + same display name → no error."""
        df = _make_df([
            ("أحمد", "قسم أ", "C01", "الرياضيات", "ث2"),
            ("سارة", "قسم أ", "C01", "الرياضيات", "ث2"),
        ])
        report = validate(df)
        assert len([e for e in _errors(report) if e["rule"] == 3]) == 0


# ─────────────────────────────────────────────────────────────────────────────
# Rule 4 — cross-department name variation is NOT an error (P1-T5)
# ─────────────────────────────────────────────────────────────────────────────

class TestRule4:
    def test_cross_dept_variation_produces_zero_errors(self):
        """Same course_id, different names in different departments → NO error."""
        df = _make_df([
            ("أحمد", "برمجيات",        "C0900", "الرياضيات المتقطعة",   "ث2"),
            ("رنا",  "تقنية معلومات",  "C0900", "رياضيات الحوسبة",      "ث2"),
            ("بدر",  "ذكاء اصطناعي",   "C0900", "أسس الرياضيات",        "ث2"),
            ("منى",  "اتصالات",         "C0900", "الجبر الخطي التطبيقي", "ث2"),
        ])
        report = validate(df)
        # Zero critical errors related to rule 3
        r3 = [e for e in _errors(report) if e["rule"] == 3]
        assert len(r3) == 0
        # is_valid may still be False for other reasons but NOT because of Rule 4


# ─────────────────────────────────────────────────────────────────────────────
# Rule 5 — same display name, different course_ids (P1-T6)
# ─────────────────────────────────────────────────────────────────────────────

class TestRule5:
    def test_flags_same_name_two_ids(self):
        df = _make_df([
            ("ياسر", "طاقة متجددة",  "C0750", "أنظمة الطاقة", "ث3"),
            ("ياسر", "ميكاترونيات",   "C0850", "أنظمة الطاقة", "ث3"),
        ])
        report = validate(df)
        r5 = [w for w in _warnings(report) if w["rule"] == 5]
        assert len(r5) == 1
        assert r5[0]["severity"] == "warning"
        assert set(r5[0]["extra"]["course_ids"]) == {"C0750", "C0850"}

    def test_unique_names_no_warning(self):
        df = _make_df([
            ("أحمد", "قسم أ", "C01", "مادة أ", "ث2"),
            ("سارة", "قسم ب", "C02", "مادة ب", "ث2"),
        ])
        report = validate(df)
        assert len([w for w in _warnings(report) if w["rule"] == 5]) == 0


# ─────────────────────────────────────────────────────────────────────────────
# Rule 6 — duplicate student names (P1-T7)
# ─────────────────────────────────────────────────────────────────────────────

class TestRule6:
    def test_flags_duplicated_name_cross_dept(self):
        """أحمد محمد علي appears in two departments with no shared course → possible dup."""
        df = _make_df([
            ("أحمد محمد علي", "شبكات الحاسوب", "C0101", "أمن الشبكات",    "ث3"),
            ("أحمد محمد علي", "اتصالات",        "C0204", "الإلكترونيات",   "ث2"),
            # same name, different dept, different course → row count (2) > unique courses (2)? No.
            # Add a true dup: same name, same course (data entry error)
            ("أحمد محمد علي", "شبكات الحاسوب", "C0101", "أمن الشبكات",    "ث3"),
        ])
        report = validate(df)
        r6 = [w for w in _warnings(report) if w["rule"] == 6]
        assert len(r6) >= 1
        assert r6[0]["severity"] == "warning"

    def test_unique_names_no_warning(self):
        df = _make_df([
            ("أحمد", "قسم أ", "C01", "مادة أ", "ث2"),
            ("سارة", "قسم ب", "C02", "مادة ب", "ث2"),
        ])
        report = validate(df)
        assert len([w for w in _warnings(report) if w["rule"] == 6]) == 0


# ─────────────────────────────────────────────────────────────────────────────
# Report structure (P1-T8)
# ─────────────────────────────────────────────────────────────────────────────

class TestReportStructure:
    def test_is_valid_false_when_errors(self):
        df = _make_df([("أحمد", "قسم", "", "مادة", "ث3")])
        report = validate(df)
        assert report["is_valid"] is False

    def test_is_valid_true_when_clean(self):
        df = _make_df([("أحمد", "قسم", "C01", "مادة", "ث3")])
        report = validate(df)
        assert report["is_valid"] is True
        assert report["errors"] == []

    def test_row_count_correct(self):
        df = _make_df([
            ("أحمد", "قسم", "C01", "مادة", "ث3"),
            ("سارة", "قسم", "C02", "مادة2", "ث3"),
        ])
        report = validate(df)
        assert report["row_count"] == 2

    def test_all_required_keys_present(self):
        df = _make_df([("أحمد", "قسم", "C01", "مادة", "ث3")])
        report = validate(df)
        for key in ("errors", "warnings", "row_count", "is_valid"):
            assert key in report

    def test_fixture_has_expected_errors(self):
        """Run the actual test_fixture.xlsx through validation and confirm seeded errors."""
        fixture_path = Path(__file__).parent.parent.parent / "fixtures" / "test_fixture.xlsx"
        if not fixture_path.exists():
            pytest.skip("test_fixture.xlsx not yet generated")
        from app.ingestion import read_excel
        df = read_excel(fixture_path.read_bytes())
        report = validate(df)
        # Should have at least 2 Critical errors (Rule 2: blank course_id; Rule 3: C0508 naming)
        assert len(report["errors"]) >= 2
        # Should have at least 1 Warning (Rule 5 or Rule 6)
        assert len(report["warnings"]) >= 1
        assert report["is_valid"] is False
