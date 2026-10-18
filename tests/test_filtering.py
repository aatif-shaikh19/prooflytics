import json
import os
import pytest
from app.schemas.analytics import BlockConfig, ReportFilter
from app.services.analytics import evaluate_block
from app.services.ingestion import parse_and_profile_csv

def test_date_range_filter():
    rows = [
        {"typed": {"date": "2024-01-10", "val": 100.0}, "structurally_valid": True},
        {"typed": {"date": "2024-02-15", "val": 200.0}, "structurally_valid": True},
        {"typed": {"date": "2024-03-20", "val": 300.0}, "structurally_valid": True},
        {"typed": {"date": "2024-04-25", "val": 400.0}, "structurally_valid": True},
        {"typed": {"date": None, "val": 500.0}, "structurally_valid": True}, # null date
    ]

    # Filter for Feb to March 2024
    flt = ReportFilter(date_column="date", start_date="2024-02-01", end_date="2024-03-31")
    res = evaluate_block(rows, BlockConfig(kind="metric", column="val", op="SUM"), report_filter=flt)

    assert res.primary_value == 500.0 # 200 + 300
    assert res.row_accounting.total_rows == 5
    assert res.row_accounting.included == 2
    assert res.row_accounting.filtered_out == 3 # Jan, Apr, and null date
    assert res.row_accounting.invalid_for_operation == 0
    assert res.row_accounting.structurally_rejected == 0

def test_category_filter():
    rows = [
        {"typed": {"dept": "Hardware", "val": 100.0}, "structurally_valid": True},
        {"typed": {"dept": "Software", "val": 200.0}, "structurally_valid": True},
        {"typed": {"dept": "Cloud", "val": 300.0}, "structurally_valid": True},
        {"typed": {"dept": "Hardware", "val": 400.0}, "structurally_valid": True},
    ]

    flt = ReportFilter(category_column="dept", selected_categories=["Hardware"])
    res = evaluate_block(rows, BlockConfig(kind="metric", column="val", op="SUM"), report_filter=flt)

    assert res.primary_value == 500.0 # 100 + 400
    assert res.row_accounting.total_rows == 4
    assert res.row_accounting.included == 2
    assert res.row_accounting.filtered_out == 2 # Software and Cloud

def test_combined_date_and_category_filter():
    rows = [
        {"typed": {"date": "2024-01-10", "dept": "Hardware", "val": 100.0}, "structurally_valid": True},
        {"typed": {"date": "2024-02-15", "dept": "Hardware", "val": 200.0}, "structurally_valid": True},
        {"typed": {"date": "2024-02-20", "dept": "Software", "val": 300.0}, "structurally_valid": True},
        {"typed": {"date": "2024-05-01", "dept": "Hardware", "val": 400.0}, "structurally_valid": True},
    ]

    flt = ReportFilter(
        date_column="date",
        start_date="2024-02-01",
        end_date="2024-03-01",
        category_column="dept",
        selected_categories=["Hardware"]
    )
    res = evaluate_block(rows, BlockConfig(kind="metric", column="val", op="SUM"), report_filter=flt)

    # Only row 2 matches both date and category
    assert res.primary_value == 200.0
    assert res.row_accounting.included == 1
    assert res.row_accounting.filtered_out == 3

def test_filter_applies_to_chart_and_table_blocks():
    rows = [
        {"typed": {"date": "2024-01-01", "dept": "Eng", "amount": 100.0}, "structurally_valid": True},
        {"typed": {"date": "2024-02-01", "dept": "Eng", "amount": 200.0}, "structurally_valid": True},
        {"typed": {"date": "2024-03-01", "dept": "Sales", "amount": 300.0}, "structurally_valid": True},
    ]

    flt = ReportFilter(category_column="dept", selected_categories=["Eng"])

    # 1. Bar Chart
    res_bar = evaluate_block(rows, BlockConfig(kind="bar_chart", column="amount", group_by_column="dept", op="SUM"), report_filter=flt)
    assert res_bar.row_accounting.included == 2
    assert res_bar.chart_data["labels"] == ["Eng"]
    assert res_bar.chart_data["datasets"][0]["data"] == [300.0]

    # 2. Line Chart
    res_line = evaluate_block(rows, BlockConfig(kind="line_chart", column="amount", group_by_column="date", op="SUM"), report_filter=flt)
    assert res_line.row_accounting.included == 2
    assert res_line.chart_data["labels"] == ["2024-01-01", "2024-02-01"]
    assert res_line.chart_data["datasets"][0]["data"] == [100.0, 200.0]

    # 3. Top-N Table
    res_table = evaluate_block(rows, BlockConfig(kind="top_n_table", column="amount", limit=5), report_filter=flt)
    assert res_table.row_accounting.included == 2
    assert len(res_table.table_data["rows"]) == 2

def test_note_block_unaffected_by_filters():
    rows = [
        {"typed": {"val": 100.0}, "structurally_valid": True},
        {"typed": {"val": 200.0}, "structurally_valid": True},
    ]

    flt = ReportFilter(category_column="nonexistent", selected_categories=["None"])
    res = evaluate_block(rows, BlockConfig(kind="note", note_text="Quarterly Note Text"), report_filter=flt)

    assert res.primary_value == "Quarterly Note Text"
    assert res.formatted_value == "Quarterly Note Text"
    assert res.row_accounting.total_rows == 2
    assert res.row_accounting.structurally_rejected == 0
    assert res.row_accounting.filtered_out == 0

def test_filter_against_synthetic_messy_fixture():
    fixture_csv = os.path.join(os.path.dirname(__file__), "..", "fixtures", "messy_sample.csv")
    expected_json = os.path.join(os.path.dirname(__file__), "..", "fixtures", "expected_results.json")

    with open(fixture_csv, "r", encoding="utf-8") as f:
        csv_text = f.read()
    with open(expected_json, "r", encoding="utf-8") as f:
        expected = json.load(f)["aggregations"]["filtered_test"]

    _, _, processed_rows = parse_and_profile_csv(csv_text)
    raw_rows = [{"typed": r["typed_json"], "structurally_valid": r["structurally_valid"]} for r in processed_rows]

    flt = ReportFilter(
        date_column="transaction_date",
        start_date="2024-03-01",
        end_date="2024-06-30",
        category_column="department",
        selected_categories=["Engineering", "Marketing"]
    )

    res = evaluate_block(raw_rows, BlockConfig(kind="metric", column="amount", op="SUM"), report_filter=flt)

    assert res.primary_value == expected["sum"]
    assert res.row_accounting.model_dump() == expected["accounting"]
    assert res.row_accounting.total_rows == (
        res.row_accounting.structurally_rejected
        + res.row_accounting.filtered_out
        + res.row_accounting.invalid_for_operation
        + res.row_accounting.included
    )
