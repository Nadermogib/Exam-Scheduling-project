"""
Generate the synthetic test fixture (P0-T6).

Produces fixtures/test_fixture.xlsx — a ~30-row Excel file with the
5-column Arabic schema from spec.md §5, containing:

  - 8 departments (same as the real sample)
  - Valid rows for normal conflict-graph testing
  - ONE Critical error: course C0508 in dept شبكات الحاسوب appears with two
    different display names (the real-world example from §6 Rule 3)
  - ONE Critical error: a blank course_id in one row (§6 Rule 2)
  - ONE Warning: same display name linked to two different course_id values
    (§6 Rule 5)
  - ONE Warning: a student name duplicated across two rows (§6 Rule 6)
  - 4 cross-department shared courses with different display names (§6 Rule 4
    — NOT an error)

Run:
    python fixtures/generate_fixture.py
"""
from __future__ import annotations

import sys
from pathlib import Path

# Allow running from any working directory
ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

import pandas as pd

COLUMNS = ["اسم الطالب", "القسم", "رمز المادة", "المقرر", "الفصل"]

DEPARTMENTS = [
    "شبكات الحاسوب",
    "اتصالات",
    "برمجيات",
    "تقنية معلومات",
    "ذكاء اصطناعي",
    "صناعية",
    "طاقة متجددة",
    "ميكاترونيات",
]

# ---------------------------------------------------------------------------
# Valid base rows — no errors
# ---------------------------------------------------------------------------
valid_rows = [
    # student,                  dept,              course_id, display_name,           level
    ("أحمد محمد علي",           "شبكات الحاسوب",  "C0101",   "أمن الشبكات",          "السنة الثالثة"),
    ("أحمد محمد علي",           "شبكات الحاسوب",  "C0102",   "بروتوكولات الشبكات",   "السنة الثالثة"),
    ("فاطمة يوسف حسن",          "اتصالات",         "C0201",   "معالجة الإشارات",      "السنة الرابعة"),
    ("فاطمة يوسف حسن",          "اتصالات",         "C0202",   "أنظمة الاتصالات",      "السنة الرابعة"),
    ("فاطمة يوسف حسن",          "اتصالات",         "C0203",   "الألياف الضوئية",      "السنة الرابعة"),
    ("محمد عبد الله سالم",      "برمجيات",         "C0301",   "هندسة البرمجيات",      "السنة الثالثة"),
    ("محمد عبد الله سالم",      "برمجيات",         "C0302",   "قواعد البيانات",       "السنة الثالثة"),
    ("نور إبراهيم خالد",        "تقنية معلومات",  "C0401",   "أمن المعلومات",        "السنة الثالثة"),
    ("نور إبراهيم خالد",        "تقنية معلومات",  "C0402",   "إدارة الشبكات",        "السنة الثالثة"),
    ("سارة أحمد الزهراني",      "ذكاء اصطناعي",   "C0501",   "تعلم الآلة",           "السنة الرابعة"),
    ("سارة أحمد الزهراني",      "ذكاء اصطناعي",   "C0502",   "الشبكات العصبية",      "السنة الرابعة"),
    ("عمر حسن المنصور",         "صناعية",          "C0601",   "الأتمتة الصناعية",     "السنة الثالثة"),
    ("عمر حسن المنصور",         "صناعية",          "C0602",   "أنظمة التحكم",         "السنة الثالثة"),
    ("ليلى عبد الرحمن",         "طاقة متجددة",    "C0701",   "الطاقة الشمسية",       "السنة الثالثة"),
    ("ليلى عبد الرحمن",         "طاقة متجددة",    "C0702",   "طاقة الرياح",          "السنة الثالثة"),
    ("كريم سعيد الغامدي",       "ميكاترونيات",     "C0801",   "الروبوتات",            "السنة الرابعة"),
    ("كريم سعيد الغامدي",       "ميكاترونيات",     "C0802",   "الأنظمة المدمجة",      "السنة الرابعة"),
    # Shared course C0900 appears in two departments with different display names
    # (§6 Rule 4 — NOT an error; this tests Rule 4 passes cleanly)
    ("طارق محمد الشهري",        "برمجيات",         "C0900",   "الرياضيات المتقطعة",   "السنة الثانية"),
    ("رنا علي الدوسري",         "تقنية معلومات",  "C0900",   "رياضيات الحوسبة",      "السنة الثانية"),
    ("بدر ناصر القحطاني",       "ذكاء اصطناعي",   "C0900",   "أسس الرياضيات",        "السنة الثانية"),
    ("منى سلطان العتيبي",       "اتصالات",         "C0900",   "الجبر الخطي التطبيقي", "السنة الثانية"),
    # Another shared course to create a conflict between C0101 and C0301
    ("سلمى جاسم الحربي",        "شبكات الحاسوب",  "C0101",   "أمن الشبكات",          "السنة الثالثة"),
    ("سلمى جاسم الحربي",        "برمجيات",         "C0301",   "هندسة البرمجيات",      "السنة الثالثة"),
]

# ---------------------------------------------------------------------------
# ERROR row 1 — Critical: C0508 in شبكات الحاسوب with TWO different names
# (real-world example from §6 Rule 3)
# ---------------------------------------------------------------------------
critical_rule3_rows = [
    ("وليد صالح العمري",  "شبكات الحاسوب",  "C0508",  "الشبكات اللاسلكية والموبايل",         "السنة الرابعة"),
    ("وليد صالح العمري",  "شبكات الحاسوب",  "C0508",  "شبكات لاسلكية والاتصالات الخلوية",    "السنة الرابعة"),
]

# ---------------------------------------------------------------------------
# ERROR row 2 — Critical: blank course_id (§6 Rule 2)
# ---------------------------------------------------------------------------
critical_rule2_rows = [
    ("هدى محمد الجهني",  "صناعية",  "",  "مادة مجهولة",  "السنة الثالثة"),
]

# ---------------------------------------------------------------------------
# WARNING row — Rule 5: same display name, different course_id
# ---------------------------------------------------------------------------
warning_rule5_rows = [
    ("ياسر عبد العزيز",  "طاقة متجددة",   "C0750",  "أنظمة الطاقة",  "السنة الثالثة"),
    ("ياسر عبد العزيز",  "ميكاترونيات",    "C0850",  "أنظمة الطاقة",  "السنة الثالثة"),
    # ↑ same المقرر "أنظمة الطاقة" with two different course_id values → Warning Rule 5
]

# ---------------------------------------------------------------------------
# WARNING row — Rule 6: duplicated student full name
# ---------------------------------------------------------------------------
warning_rule6_rows = [
    ("أحمد محمد علي",  "اتصالات",  "C0204",  "الإلكترونيات",  "السنة الثانية"),
    # ↑ "أحمد محمد علي" already appears in شبكات الحاسوب above → Warning Rule 6
]

# ---------------------------------------------------------------------------
# Assemble and save
# ---------------------------------------------------------------------------
all_rows = (
    valid_rows
    + critical_rule3_rows
    + critical_rule2_rows
    + warning_rule5_rows
    + warning_rule6_rows
)

df = pd.DataFrame(all_rows, columns=COLUMNS)

OUT_PATH = ROOT / "fixtures" / "test_fixture.xlsx"
with pd.ExcelWriter(OUT_PATH, engine="openpyxl") as writer:
    df.to_excel(writer, index=False, sheet_name="تسجيل الطلاب")

    # Apply basic RTL formatting to the sheet
    ws = writer.sheets["تسجيل الطلاب"]
    ws.sheet_view.rightToLeft = True

    # Widen columns for readability
    col_widths = [30, 22, 12, 40, 18]
    for i, width in enumerate(col_widths, start=1):
        ws.column_dimensions[ws.cell(row=1, column=i).column_letter].width = width

print(f"[OK] Fixture written to {OUT_PATH}")
print(f"  Rows: {len(df)}")
print(f"  Unique students: {df['اسم الطالب'].nunique()}")
print(f"  Unique course_ids: {df['رمز المادة'].nunique()}")
print()
print("Seeded errors:")
print("  Critical — Rule 3 (same course_id + dept, two display names): C0508 in شبكات الحاسوب")
print("  Critical — Rule 2 (blank course_id): row with هدى محمد الجهني")
print("  Warning  — Rule 5 (same display name, different course_ids): أنظمة الطاقة / C0750 vs C0850")
print("  Warning  — Rule 6 (duplicate student name): أحمد محمد علي")
print("  Rule 4   — shared C0900 across 4 departments (NOT an error)")
