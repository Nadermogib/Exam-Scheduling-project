"""
Excel ingestion helper.

Reads an uploaded .xlsx file into a normalised pandas DataFrame with
consistent English internal column names (mapped from the Arabic source
headers defined in spec.md §5).

Column mapping
--------------
  Arabic source header     →  internal name
  ─────────────────────────────────────────
  اسم الطالب              →  student_name
  القسم                   →  department
  رمز المادة              →  course_id
  المقرر                  →  course_display_name
  الفصل                   →  academic_level
"""
from __future__ import annotations

from io import BytesIO
from typing import BinaryIO

import pandas as pd

# Authoritative Arabic column names (spec.md §5)
ARABIC_COLS = {
    "اسم الطالب": "student_name",
    "القسم": "department",
    "رمز المادة": "course_id",
    "المقرر": "course_display_name",
    "الفصل": "academic_level",
}

REQUIRED_ARABIC = list(ARABIC_COLS.keys())
INTERNAL_COLS = list(ARABIC_COLS.values())


class IngestionError(ValueError):
    """Raised when the file cannot be parsed at all (wrong format, missing sheet, etc.)."""


def read_excel(file_bytes: bytes) -> pd.DataFrame:
    """
    Parse *file_bytes* (raw .xlsx content) into a normalised DataFrame.

    Returns a DataFrame with columns: student_name, department, course_id,
    course_display_name, academic_level.

    All string values are stripped of leading/trailing whitespace.
    Row index is 1-based to match Excel row numbers (header = row 1, data starts row 2).

    Raises IngestionError if the file cannot be parsed or required columns are missing.
    """
    try:
        raw = pd.read_excel(BytesIO(file_bytes), dtype=str, header=None)
    except Exception as exc:
        raise IngestionError(f"تعذّر قراءة الملف: {exc}") from exc

    if raw.empty:
        raise IngestionError("الملف فارغ أو لا يحتوي على بيانات.")

    # Find the header row (search first 20 rows)
    header_idx = -1
    for idx, row in raw.head(20).iterrows():
        # Check if this row has all the required columns
        row_vals = set(str(v).strip() for v in row.values if pd.notna(v))
        if all(col in row_vals for col in REQUIRED_ARABIC):
            header_idx = idx
            break
            
    if header_idx == -1:
        raise IngestionError(
            f"لم يتم العثور على الأعمدة المطلوبة في الملف. يرجى التأكد من وجود: {', '.join(REQUIRED_ARABIC)}"
        )

    # Re-read or just update columns
    raw.columns = [str(c).strip() for c in raw.iloc[header_idx]]
    raw = raw.iloc[header_idx + 1:].reset_index(drop=True)

    # Select and rename
    df = raw[REQUIRED_ARABIC].rename(columns=ARABIC_COLS).copy()

    # Normalise strings: strip whitespace; convert NaN → empty string
    for col in INTERNAL_COLS:
        df[col] = df[col].fillna("").astype(str).str.strip()

    # Offset row index so error messages report the correct Excel row number
    # Excel is 1-indexed. header_idx is 0-indexed.
    # Data starts at header_idx + 2 in Excel terms.
    df.index = range(header_idx + 2, header_idx + 2 + len(df))

    return df
