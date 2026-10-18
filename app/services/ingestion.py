"""
Auditable CSV Ingestion, Parsing, Profiling, and Persistence Service for Prooflytics.

Key invariants:
1. Bounded upload size (default 5 MiB max).
2. Strict UTF-8 handling (accepts UTF-8 BOM, rejects non-UTF8/binary).
3. Non-dropping: preserves original row numbers, raw values, and explicit failure reasons.
4. Unrecoverable quote/syntax errors explicitly rejected with diagnostics (no fake recovery).
5. Deterministic type inference and mutually exclusive row classification:
   total_rows = accepted_rows + warning_rows + rejected_rows.
"""
import csv
import io
import json
from typing import Any, Dict, List, Optional, Tuple
from sqlalchemy.orm import Session
from app.config import settings
from app.db.models import Dataset, DatasetRow
from app.services.types import infer_column_type, is_blank, validate_and_coerce_cell

class IngestionError(Exception):
    """Base exception for CSV ingestion errors."""
    pass

class OversizedFileError(IngestionError):
    """Raised when file exceeds byte limit."""
    pass

class EncodingError(IngestionError):
    """Raised when file is not valid UTF-8 text."""
    pass

class MalformedCSVError(IngestionError):
    """Raised when CSV structure or quoting is unparseable."""
    pass

class EmptyCSVError(IngestionError):
    """Raised when CSV has no content or missing headers."""
    pass

def read_and_validate_bytes(
    content_bytes: bytes,
    max_bytes: int = settings.MAX_UPLOAD_BYTES
) -> str:
    """
    Validate byte length and decode strictly as UTF-8 (supporting UTF-8 BOM).
    Rejects binary files containing null bytes.
    """
    if len(content_bytes) > max_bytes:
        raise OversizedFileError(
            f"File size ({len(content_bytes):,} bytes) exceeds maximum allowed limit ({max_bytes:,} bytes / 5 MiB)."
        )

    # Detect binary content (null bytes)
    if b"\x00" in content_bytes[:4096]:
        raise MalformedCSVError("File appears to be a binary file, not valid text CSV.")

    try:
        # utf-8-sig seamlessly strips BOM if present, otherwise decodes standard UTF-8
        decoded_text = content_bytes.decode("utf-8-sig")
    except UnicodeDecodeError as e:
        raise EncodingError(
            f"Invalid file encoding: File must be UTF-8 encoded text. (Error at byte {e.start}: {e.reason})"
        )

    return decoded_text

def parse_and_profile_csv(
    csv_text: str
) -> Tuple[List[str], Dict[str, Any], List[Dict[str, Any]]]:
    """
    Parse CSV text, infer column types, validate cell values, and produce
    a complete profile with reconciled disjoint row counts.

    Returns:
        (headers, profile_dict, processed_rows_data)
    """
    if not csv_text.strip():
        raise EmptyCSVError("Uploaded CSV is empty.")

    string_io = io.StringIO(csv_text)
    # Use strict=True so malformed quotes raise csv.Error instead of silent corruption
    reader = csv.reader(string_io, strict=True)

    try:
        headers_raw = next(reader, None)
    except csv.Error as e:
        raise MalformedCSVError(f"Malformed CSV header: {str(e)}")

    if not headers_raw or all(is_blank(h) for h in headers_raw):
        raise EmptyCSVError("CSV is missing a valid header row.")

    # Clean headers and ensure uniqueness
    headers: List[str] = []
    seen_headers: Dict[str, int] = {}
    for idx, h in enumerate(headers_raw):
        col_name = h.strip() if h and h.strip() else f"column_{idx + 1}"
        if col_name in seen_headers:
            seen_headers[col_name] += 1
            col_name = f"{col_name}_{seen_headers[col_name]}"
        else:
            seen_headers[col_name] = 1
        headers.append(col_name)

    num_cols = len(headers)
    raw_rows_data: List[Dict[str, Any]] = []

    # First pass: read rows, preserve source row numbers and detect ragged rows
    current_line = 2
    try:
        for row in reader:
            source_row_num = current_line
            current_line += 1

            is_ragged = len(row) != num_cols
            issues: List[Dict[str, Any]] = []

            if is_ragged:
                issues.append({
                    "column": None,
                    "issue": "ragged_row",
                    "detail": f"Expected {num_cols} columns, found {len(row)}"
                })

            # Map raw cell strings
            raw_dict: Dict[str, str] = {}
            for i in range(num_cols):
                raw_dict[headers[i]] = row[i] if i < len(row) else ""

            raw_rows_data.append({
                "source_row_number": source_row_num,
                "raw_values": raw_dict,
                "structurally_valid": not is_ragged,
                "initial_issues": issues
            })
    except csv.Error as e:
        raise MalformedCSVError(f"Unrecoverable malformed CSV syntax around row {current_line}: {str(e)}")

    total_rows = len(raw_rows_data)

    # Second pass: Type inference per column
    column_values: Dict[str, List[Optional[str]]] = {h: [] for h in headers}
    for r in raw_rows_data:
        for h in headers:
            column_values[h].append(r["raw_values"].get(h))

    column_types: Dict[str, str] = {}
    for h in headers:
        column_types[h] = infer_column_type(column_values[h])

    # Third pass: Validate cells, assign typed values, and classify row status
    processed_rows: List[Dict[str, Any]] = []
    column_profiles: Dict[str, Dict[str, Any]] = {
        h: {
            "name": h,
            "inferred_type": column_types[h],
            "total_count": total_rows,
            "non_blank_count": 0,
            "blank_count": 0,
            "invalid_count": 0,
            "sample_values": []
        }
        for h in headers
    }

    accepted_rows = 0
    warning_rows = 0
    rejected_rows = 0
    all_row_issues_sample: List[Dict[str, Any]] = []

    for r in raw_rows_data:
        source_row_num = r["source_row_number"]
        structurally_valid = r["structurally_valid"]
        raw_dict = r["raw_values"]
        typed_dict: Dict[str, Any] = {}
        row_issues: List[Dict[str, Any]] = list(r["initial_issues"])

        has_type_error = False
        has_blank_cell = False

        for h in headers:
            raw_val = raw_dict.get(h)
            col_type = column_types[h]
            typed_val, cell_issue = validate_and_coerce_cell(h, raw_val, col_type)
            typed_dict[h] = typed_val

            col_prof = column_profiles[h]
            if is_blank(raw_val):
                col_prof["blank_count"] += 1
                has_blank_cell = True
            else:
                col_prof["non_blank_count"] += 1
                if len(col_prof["sample_values"]) < 5 and raw_val not in col_prof["sample_values"]:
                    col_prof["sample_values"].append(raw_val)

            if cell_issue:
                row_issues.append(cell_issue)
                if cell_issue["issue"] in ("invalid_number", "invalid_date"):
                    has_type_error = True
                    col_prof["invalid_count"] += 1

        # Mutually exclusive classification:
        # Rejected: structurally invalid (ragged) OR has unparseable cells for typed columns
        # Warning: structurally valid, no type errors, but has blank cells
        # Accepted: structurally valid, no type errors, complete non-blank values
        if not structurally_valid or has_type_error:
            row_status = "rejected"
            rejected_rows += 1
        elif has_blank_cell:
            row_status = "warning"
            warning_rows += 1
        else:
            row_status = "accepted"
            accepted_rows += 1

        if row_issues and len(all_row_issues_sample) < 50:
            all_row_issues_sample.append({
                "source_row_number": source_row_num,
                "status": row_status,
                "issues": row_issues,
                "raw_values": raw_dict
            })

        processed_rows.append({
            "source_row_number": source_row_num,
            "raw_json": json.dumps(raw_dict),
            "typed_json": json.dumps(typed_dict),
            "issues_json": json.dumps(row_issues),
            "structurally_valid": structurally_valid,
            "status": row_status
        })

    # Invariant assertion
    assert total_rows == (accepted_rows + warning_rows + rejected_rows), "Row counts must reconcile exactly!"

    schema_dict = {
        "columns": [
            {
                "name": h,
                "type": column_types[h],
                "blank_count": column_profiles[h]["blank_count"],
                "invalid_count": column_profiles[h]["invalid_count"]
            }
            for h in headers
        ]
    }

    profile_dict = {
        "total_rows": total_rows,
        "accepted_rows": accepted_rows,
        "warning_rows": warning_rows,
        "rejected_rows": rejected_rows,
        "columns": list(column_profiles.values()),
        "column_names": headers,
        "issues_sample": all_row_issues_sample
    }

    return headers, profile_dict, processed_rows

def ingest_dataset_from_bytes(
    db: Session,
    owner_id: str,
    original_filename: str,
    dataset_name: str,
    content_bytes: bytes,
    max_bytes: int = settings.MAX_UPLOAD_BYTES
) -> Dataset:
    """
    End-to-end ingestion orchestrator:
    Reads bytes, validates size/encoding/syntax, profiles, and persists Dataset and DatasetRow records.
    """
    csv_text = read_and_validate_bytes(content_bytes, max_bytes=max_bytes)
    headers, profile_dict, processed_rows = parse_and_profile_csv(csv_text)

    schema_dict = {
        "columns": [
            {
                "name": c["name"],
                "type": c["inferred_type"],
                "blank_count": c["blank_count"],
                "invalid_count": c["invalid_count"]
            }
            for c in profile_dict["columns"]
        ]
    }

    dataset = Dataset(
        owner_id=owner_id,
        name=dataset_name or original_filename,
        original_filename=original_filename,
        status="ready",
        row_count=profile_dict["total_rows"],
        schema_json=json.dumps(schema_dict),
        profile_json=json.dumps(profile_dict)
    )
    db.add(dataset)
    db.commit()
    db.refresh(dataset)

    # Persist dataset rows in batches
    batch_size = 500
    row_objects: List[DatasetRow] = []
    for r in processed_rows:
        row_obj = DatasetRow(
            dataset_id=dataset.id,
            source_row_number=r["source_row_number"],
            raw_json=r["raw_json"],
            typed_json=r["typed_json"],
            issues_json=r["issues_json"],
            structurally_valid=r["structurally_valid"]
        )
        row_objects.append(row_obj)
        if len(row_objects) >= batch_size:
            db.bulk_save_objects(row_objects)
            db.commit()
            row_objects.clear()

    if row_objects:
        db.bulk_save_objects(row_objects)
        db.commit()

    return dataset
