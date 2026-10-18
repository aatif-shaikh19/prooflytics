"""
Deterministic column type inference and cell validation for Prooflytics.

Rules and thresholds:
1. Number: >= 90% of non-blank cells successfully parse as numeric (integer/float/decimal).
2. Date: >= 90% of non-blank cells successfully parse as valid calendar dates.
3. Category: Non-numeric, non-date column where distinct non-blank count <= 20 and ratio <= 0.3 (or small sample <= 30 rows).
4. Text: Fallback for freeform strings, ambiguous columns, or columns where all values are blank.

Never silently drop or mutate raw values; invalid cells are marked with explicit reasons.
"""
from datetime import datetime
import re
from typing import Any, Dict, List, Optional, Tuple

NUMBER_REGEX = re.compile(r"^-?\d+(\.\d+)?$")
DATE_FORMATS = [
    "%Y-%m-%d",
    "%Y/%m/%d",
    "%m/%d/%Y",
    "%d/%m/%Y",
    "%Y-%m-%d %H:%M:%S",
    "%Y-%m-%dT%H:%M:%S",
    "%Y-%m-%dT%H:%M:%S.%f",
]

def is_blank(value: Optional[str]) -> bool:
    """Check if a raw cell value is blank (None, empty, or whitespace-only)."""
    return value is None or str(value).strip() == ""

def try_parse_number(value: str) -> Optional[float]:
    """
    Attempt to parse a non-blank string into a float.
    Handles standard numbers, negative signs, and strip currency/commas if cleanly numeric.
    Returns float if valid, None otherwise.
    """
    if is_blank(value):
        return None
    cleaned = value.strip()
    # Strip common currency symbols or commas if they surround a clean number
    cleaned = cleaned.replace("$", "").replace("€", "").replace("£", "").replace(",", "")
    if NUMBER_REGEX.match(cleaned):
        try:
            return float(cleaned)
        except (ValueError, OverflowError):
            return None
    return None

def try_parse_date(value: str) -> Optional[str]:
    """
    Attempt to parse a non-blank string into a normalized ISO date string (YYYY-MM-DD).
    Validates calendar boundaries (rejects invalid dates like 2024-02-30).
    Returns ISO date string if valid, None otherwise.
    """
    if is_blank(value):
        return None
    cleaned = value.strip()
    for fmt in DATE_FORMATS:
        try:
            dt = datetime.strptime(cleaned, fmt)
            return dt.strftime("%Y-%m-%d")
        except (ValueError, TypeError):
            continue
    return None

def infer_column_type(values: List[Optional[str]]) -> str:
    """
    Infer column type deterministically based on documented thresholds.
    Returns: 'number', 'date', 'category', or 'text'.
    """
    non_blank_values = [v.strip() for v in values if not is_blank(v)]
    total_non_blank = len(non_blank_values)

    if total_non_blank == 0:
        return "text"

    # 1. Number threshold: >= 90% of non-blank values
    valid_numbers = sum(1 for v in non_blank_values if try_parse_number(v) is not None)
    if (valid_numbers / total_non_blank) >= 0.90:
        return "number"

    # 2. Date threshold: >= 90% of non-blank values
    valid_dates = sum(1 for v in non_blank_values if try_parse_date(v) is not None)
    if (valid_dates / total_non_blank) >= 0.90:
        return "date"

    # 3. Category threshold: distinct values bounded
    distinct_count = len(set(non_blank_values))
    distinct_ratio = distinct_count / total_non_blank
    if distinct_count <= 20 and (distinct_ratio <= 0.30 or total_non_blank <= 30):
        return "category"

    # 4. Fallback to text
    return "text"

def validate_and_coerce_cell(
    column_name: str,
    raw_value: Optional[str],
    inferred_type: str
) -> Tuple[Optional[Any], Optional[Dict[str, Any]]]:
    """
    Coerce a single cell based on its column's inferred type.
    Returns (typed_value, issue_dict_or_None).
    """
    if is_blank(raw_value):
        return None, {"column": column_name, "issue": "blank_cell", "raw_value": raw_value}

    cleaned = raw_value.strip()

    if inferred_type == "number":
        num = try_parse_number(cleaned)
        if num is not None:
            return num, None
        return None, {"column": column_name, "issue": "invalid_number", "raw_value": raw_value}

    if inferred_type == "date":
        iso_date = try_parse_date(cleaned)
        if iso_date is not None:
            return iso_date, None
        return None, {"column": column_name, "issue": "invalid_date", "raw_value": raw_value}

    if inferred_type == "category":
        return cleaned, None

    # Default 'text'
    return cleaned, None
