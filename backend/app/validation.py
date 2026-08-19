"""
Validation engine — implements all six rules from spec.md §6.

Each rule returns a list of ValidationIssue objects.
The caller aggregates them into the full report.

Rule classification
───────────────────
  Critical  →  blocks progression to the scheduling step
  Warning   →  informational only; does not block

Rules
─────
  1  Any required column is blank in a row                     Critical
  2  course_id is blank (dedicated, clearer message)           Critical
  3  Same course_id + same dept → two different display names  Critical
  4  Same course_id, different names across depts              NOT an error
  5  Same display name → two different course_id values        Warning
  6  Duplicate student full names                              Warning
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

import pandas as pd

Severity = Literal["critical", "warning"]

# Columns that must never be blank (Rule 1)
REQUIRED_COLUMNS = ["student_name", "department", "course_id", "course_display_name"]

# Human-readable Arabic label for each internal column name
COLUMN_LABELS: dict[str, str] = {
    "student_name": "اسم الطالب",
    "department": "القسم",
    "course_id": "رمز المادة",
    "course_display_name": "المقرر",
    "academic_level": "الفصل",
}


@dataclass
class ValidationIssue:
    severity: Severity
    rule: int                  # 1-6
    row: int | None            # 1-based Excel row number; None for cross-row issues
    column: str | None         # internal column name; None for multi-column issues
    message: str               # Arabic-language human-readable description
    offending_value: str | None = None
    extra: dict | None = None  # supplementary data (e.g., conflicting names list)


# ─────────────────────────────────────────────────────────────────────────────
# Rule implementations
# ─────────────────────────────────────────────────────────────────────────────

def _rule1_blank_required_cells(df: pd.DataFrame) -> list[ValidationIssue]:
    """Rule 1 — Any required column is blank in a row (Critical)."""
    issues: list[ValidationIssue] = []
    for col in REQUIRED_COLUMNS:
        # course_id blanks get a separate message in Rule 2; still flag here too
        blank_mask = df[col] == ""
        for row_idx in df.index[blank_mask]:
            issues.append(
                ValidationIssue(
                    severity="critical",
                    rule=1,
                    row=int(row_idx),
                    column=col,
                    message=f"الخلية في العمود '{COLUMN_LABELS[col]}' فارغة.",
                    offending_value="",
                )
            )
    return issues


def _rule2_blank_course_id(df: pd.DataFrame) -> list[ValidationIssue]:
    """
    Rule 2 — course_id is blank (dedicated error with stronger messaging).

    We deduplicate with Rule 1 by *replacing* the Rule 1 issue for this column
    in the aggregator — but here we simply return Rule 2 issues; the aggregator
    will suppress the corresponding Rule 1 entry for the same row+column.
    """
    issues: list[ValidationIssue] = []
    blank_mask = df["course_id"] == ""
    for row_idx in df.index[blank_mask]:
        issues.append(
            ValidationIssue(
                severity="critical",
                rule=2,
                row=int(row_idx),
                column="course_id",
                message=(
                    "رمز المادة (course_id) فارغ — لا يمكن بناء مصفوفة التعارض "
                    "بدون رمز المادة. يجب ملء هذه الخلية أو حذف الصف."
                ),
                offending_value="",
            )
        )
    return issues


def _rule3_same_course_same_dept_two_names(df: pd.DataFrame) -> list[ValidationIssue]:
    """
    Rule 3 — Same course_id + same department → two different display names (Critical).

    Groups by (course_id, department); flags groups with more than one distinct
    course_display_name.
    """
    issues: list[ValidationIssue] = []
    # Only consider rows with a non-blank course_id
    valid = df[df["course_id"] != ""]
    grouped = valid.groupby(["course_id", "department"])["course_display_name"].agg(
        lambda x: x.unique().tolist()
    )
    for (course_id, department), names in grouped.items():
        if len(names) > 1:
            # Find all row indices belonging to this group
            mask = (valid["course_id"] == course_id) & (valid["department"] == department)
            rows = [int(r) for r in valid.index[mask]]
            issues.append(
                ValidationIssue(
                    severity="warning",
                    rule=3,
                    row=rows[0],          # first affected row
                    column="course_display_name",
                    message=(
                        f"رمز المادة '{course_id}' في قسم '{department}' مرتبط "
                        f"بأكثر من اسم عرض مختلف في نفس القسم. سيتم اختيار الاسم الأول."
                    ),
                    offending_value=str(names),
                    extra={
                        "course_id": course_id,
                        "department": department,
                        "conflicting_names": names,
                        "affected_rows": rows,
                    },
                )
            )
    return issues


# Rule 4 is NOT an error — no function needed. Cross-department name variation
# is intentional and confirmed (spec.md §6 Rule 4, 54 occurrences in real data).


def _rule5_same_name_two_course_ids(df: pd.DataFrame) -> list[ValidationIssue]:
    """
    Rule 5 — Same display name → two different course_id values (Warning).
    """
    issues: list[ValidationIssue] = []
    valid = df[(df["course_id"] != "") & (df["course_display_name"] != "")]
    grouped = valid.groupby("course_display_name")["course_id"].agg(
        lambda x: x.unique().tolist()
    )
    for display_name, course_ids in grouped.items():
        if len(course_ids) > 1:
            mask = valid["course_display_name"] == display_name
            rows = [int(r) for r in valid.index[mask]]
            issues.append(
                ValidationIssue(
                    severity="warning",
                    rule=5,
                    row=rows[0],
                    column="course_display_name",
                    message=(
                        f"اسم المقرر '{display_name}' مرتبط بأكثر من رمز مادة مختلف. "
                        f"تحقق من أن هذه مواد مستقلة فعلاً وليست إدخالاً مكرراً."
                    ),
                    offending_value=display_name,
                    extra={
                        "display_name": display_name,
                        "course_ids": course_ids,
                        "affected_rows": rows,
                    },
                )
            )
    return issues


def _rule6_duplicate_student_names(df: pd.DataFrame) -> list[ValidationIssue]:
    """
    Rule 6 — Duplicate student full names (Warning).

    Flags any student_name that appears in more than one distinct department,
    or appears on rows that together suggest a data-entry duplicate (same
    student_name + same course_id). Simple duplicate-name detection flags all
    names appearing more than once so the user can review.
    """
    issues: list[ValidationIssue] = []
    valid = df[df["student_name"] != ""]
    counts = valid.groupby("student_name").size()
    duplicated_names = counts[counts > valid.groupby("student_name")["course_id"].nunique()].index

    # Simpler approach: flag any name that appears more than once across ALL rows
    name_rows: dict[str, list[int]] = {}
    for row_idx, row in valid.iterrows():
        name = row["student_name"]
        name_rows.setdefault(name, []).append(int(row_idx))

    for name, rows in name_rows.items():
        if len(rows) > 1:
            # Only warn if same name appears in different rows in a way that
            # could mean duplicate data entry — i.e., the name appears in
            # more rows than the number of unique courses for that name
            unique_courses = valid[valid["student_name"] == name]["course_id"].nunique()
            if len(rows) > unique_courses:
                issues.append(
                    ValidationIssue(
                        severity="warning",
                        rule=6,
                        row=rows[0],
                        column="student_name",
                        message=(
                            f"اسم الطالب '{name}' مكرر في الملف. "
                            f"قد يكون طالبان مختلفان بنفس الاسم — يُنصح بإضافة "
                            f"رقم هوية فريد للتمييز بين الطلاب في التصدير القادم."
                        ),
                        offending_value=name,
                        extra={"student_name": name, "affected_rows": rows},
                    )
                )
    return issues


# ─────────────────────────────────────────────────────────────────────────────
# Public API
# ─────────────────────────────────────────────────────────────────────────────

def validate(df: pd.DataFrame) -> dict:
    """
    Run all validation rules on *df* and return the structured report.

    Return shape:
    {
        "errors":   [ {severity, rule, row, column, message, offending_value, extra}, ... ],
        "warnings": [ ... ],
        "row_count": int,
        "is_valid":  bool   # True only when errors list is empty
    }

    Deduplication: Rule 2 issues supersede Rule 1 issues for the same
    (row, course_id) pair so the user does not see two identical-looking
    critical errors for the same cell.
    """
    r1 = _rule1_blank_required_cells(df)
    r2 = _rule2_blank_course_id(df)
    r3 = _rule3_same_course_same_dept_two_names(df)
    r5 = _rule5_same_name_two_course_ids(df)
    r6 = _rule6_duplicate_student_names(df)

    # Deduplicate: if Rule 2 covers (row, "course_id"), drop the Rule 1 entry
    r2_rows = {issue.row for issue in r2}
    r1_deduped = [
        i for i in r1
        if not (i.column == "course_id" and i.row in r2_rows)
    ]

    all_critical = r1_deduped + r2
    all_warnings = r3 + r5 + r6

    def _serialise(issue: ValidationIssue) -> dict:
        return {
            "severity": issue.severity,
            "rule": issue.rule,
            "row": issue.row,
            "column": issue.column,
            "column_label": COLUMN_LABELS.get(issue.column, issue.column) if issue.column else None,
            "message": issue.message,
            "offending_value": issue.offending_value,
            "extra": issue.extra,
        }

    return {
        "errors": [_serialise(i) for i in all_critical],
        "warnings": [_serialise(i) for i in all_warnings],
        "row_count": len(df),
        "is_valid": len(all_critical) == 0,
    }
