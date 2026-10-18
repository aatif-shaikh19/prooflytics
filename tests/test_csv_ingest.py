import json
import os
import io
import pytest
from app.services.ingestion import (
    parse_and_profile_csv,
    read_and_validate_bytes,
    EncodingError,
    MalformedCSVError,
    OversizedFileError,
    EmptyCSVError
)
from app.services.types import infer_column_type, try_parse_date, try_parse_number

def test_type_inference_number():
    values = ["10", "20.5", "-30", "40", "N/A", "50", "60", "70", "80", "90"]
    # 9 valid numbers out of 10 non-blank = 90% -> number
    assert infer_column_type(values) == "number"

def test_type_inference_date():
    values = [
        "2024-01-01", "2024-01-02", "2024-01-03", "2024-01-04", "2024-01-05",
        "2024-01-06", "2024-01-07", "2024-01-08", "2024-01-09", "bad-date"
    ]
    # 9 valid dates out of 10 non-blank = 90% -> date
    assert infer_column_type(values) == "date"

def test_type_inference_category():
    values = ["Engineering", "Marketing", "Sales", "Engineering", "Marketing"] * 10
    # 3 distinct values, low ratio -> category
    assert infer_column_type(values) == "category"

def test_type_inference_text_fallback():
    # High cardinality freeform strings
    values = [f"Unique description string {i}" for i in range(100)]
    assert infer_column_type(values) == "text"

def test_type_inference_all_blank():
    values = ["", "  ", None, ""]
    assert infer_column_type(values) == "text"

def test_read_bytes_valid_utf8_and_bom():
    raw_utf8 = "col1,col2\nval1,val2".encode("utf-8")
    assert read_and_validate_bytes(raw_utf8).startswith("col1,col2")

    # With UTF-8 BOM
    raw_bom = b"\xef\xbb\xbfcol1,col2\nval1,val2"
    decoded = read_and_validate_bytes(raw_bom)
    assert decoded.startswith("col1,col2")
    assert not decoded.startswith("\ufeff")

def test_read_bytes_invalid_utf8_rejected():
    invalid_bytes = b"\x80\x81invalid utf-8 text sequence"
    with pytest.raises(EncodingError):
        read_and_validate_bytes(invalid_bytes)

def test_read_bytes_binary_file_rejected():
    binary_bytes = b"PK\x03\x04\x00\x00fakezipbinarycontent"
    with pytest.raises(MalformedCSVError):
        read_and_validate_bytes(binary_bytes)

def test_read_bytes_oversized_rejected():
    oversized = b"a" * (5 * 1024 * 1024 + 10)
    with pytest.raises(OversizedFileError):
        read_and_validate_bytes(oversized, max_bytes=5 * 1024 * 1024)

def test_empty_csv_rejected():
    with pytest.raises(EmptyCSVError):
        parse_and_profile_csv("")

    with pytest.raises(EmptyCSVError):
        parse_and_profile_csv("   \n\n  ")

def test_unrecoverable_malformed_quote_rejected():
    # Broken quotation in CSV that cannot be recovered reliably
    broken_csv = 'header1,header2\n"unclosed quote value,value2\nnextrow1,nextrow2'
    # Strict csv parser raises csv.Error on unescaped or unclosed quotes
    with pytest.raises(MalformedCSVError) as exc_info:
        parse_and_profile_csv(broken_csv)
    assert "malformed" in str(exc_info.value).lower()

def test_ragged_rows_preserved_without_silent_drop():
    csv_content = """id,category,amount
1,Hardware,100
2,Software
3,Cloud,300,ExtraColumn
4,Hardware,400"""
    headers, profile, rows = parse_and_profile_csv(csv_content)
    assert headers == ["id", "category", "amount"]
    assert profile["total_rows"] == 4
    # Row 2 (short) and Row 3 (extra) are ragged
    assert profile["rejected_rows"] == 2
    assert profile["accepted_rows"] == 2

    # Verify original rows and raw values are completely preserved
    assert len(rows) == 4
    row_2 = rows[1]
    assert row_2["source_row_number"] == 3
    assert row_2["structurally_valid"] is False
    assert "ragged_row" in row_2["issues_json"]

    row_3 = rows[2]
    assert row_3["source_row_number"] == 4
    assert row_3["structurally_valid"] is False

def test_quoted_delimiters_and_multiline_cells():
    csv_content = '''id,title,comment
1,"Milestone, Phase 1","Simple comment"
2,"Milestone, Phase 2","First line\nSecond line after break"'''
    headers, profile, rows = parse_and_profile_csv(csv_content)
    assert headers == ["id", "title", "comment"]
    assert profile["total_rows"] == 2
    assert profile["accepted_rows"] == 2
    row_1_raw = json.loads(rows[0]["raw_json"])
    assert row_1_raw["title"] == "Milestone, Phase 1"
    row_2_raw = json.loads(rows[1]["raw_json"])
    assert "\n" in row_2_raw["comment"]

def test_upload_api_synthetic_messy_fixture(auth_client_a):
    client, _, _ = auth_client_a
    fixture_path = os.path.join(os.path.dirname(__file__), "..", "fixtures", "messy_sample.csv")
    expected_path = os.path.join(os.path.dirname(__file__), "..", "fixtures", "expected_results.json")

    assert os.path.exists(fixture_path), "Fixture messy_sample.csv must exist"
    assert os.path.exists(expected_path), "Fixture expected_results.json must exist"

    with open(fixture_path, "rb") as f:
        file_bytes = f.read()

    with open(expected_path, "r", encoding="utf-8") as f:
        expected = json.load(f)

    response = client.post(
        "/datasets/api/upload",
        files={"csv_file": ("messy_sample.csv", file_bytes, "text/csv")},
        data={"dataset_name": "Synthetic Messy Audit"}
    )
    assert response.status_code == 200
    data = response.json()

    # Reconcile exact counts with expected results
    assert data["total_rows"] == expected["total_rows"]
    assert data["accepted_rows"] == expected["accepted_rows"]
    assert data["warning_rows"] == expected["warning_rows"]
    assert data["rejected_rows"] == expected["rejected_rows"]

    # Reconcile disjoint count invariant
    assert data["total_rows"] == data["accepted_rows"] + data["warning_rows"] + data["rejected_rows"]

    # Verify column types match expected
    col_types = {c["name"]: c["inferred_type"] for c in data["columns"]}
    assert col_types == expected["column_types"]

    dataset_id = data["id"]

    # Fetch rows API and ensure rows can be audited
    rows_res = client.get(f"/datasets/{dataset_id}/rows/api?limit=50")
    assert rows_res.status_code == 200
    rows_data = rows_res.json()
    assert len(rows_data) == 50
    assert rows_data[0]["source_row_number"] == 2

def test_cross_tenant_isolation_on_uploaded_dataset(auth_client_a, auth_client_b):
    client_a, _, _ = auth_client_a
    client_b, _, _ = auth_client_b

    # User A uploads a dataset
    csv_bytes = b"id,val\n1,10\n2,20"
    upload_res = client_a.post(
        "/datasets/api/upload",
        files={"csv_file": ("private_a.csv", csv_bytes, "text/csv")},
        data={"dataset_name": "Private A Data"}
    )
    assert upload_res.status_code == 200
    dataset_a_id = upload_res.json()["id"]

    # User A can view it (HTML profile and rows API)
    assert client_a.get(f"/datasets/{dataset_a_id}").status_code == 200
    assert client_a.get(f"/datasets/{dataset_a_id}/api").status_code == 200
    assert client_a.get(f"/datasets/{dataset_a_id}/rows/api").status_code == 200

    # User B MUST NOT be able to view it (must return 404 Not Found to prevent existence disclosure)
    assert client_b.get(f"/datasets/{dataset_a_id}").status_code == 404
    assert client_b.get(f"/datasets/{dataset_a_id}/api").status_code == 404
    assert client_b.get(f"/datasets/{dataset_a_id}/rows/api").status_code == 404

def test_upload_oversized_file_via_api(auth_client_a):
    client, _, _ = auth_client_a
    huge_bytes = b"a" * (5 * 1024 * 1024 + 50)
    response = client.post(
        "/datasets/api/upload",
        files={"csv_file": ("huge.csv", huge_bytes, "text/csv")}
    )
    assert response.status_code == 413
    assert "exceeds maximum allowed limit" in response.json()["detail"]

def test_upload_invalid_utf8_via_api(auth_client_a):
    client, _, _ = auth_client_a
    bad_utf8 = b"\x80\x81not utf8 content"
    response = client.post(
        "/datasets/api/upload",
        files={"csv_file": ("bad_utf8.csv", bad_utf8, "text/csv")}
    )
    assert response.status_code == 400
    assert "UTF-8" in response.json()["detail"]
