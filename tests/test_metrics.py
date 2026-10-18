import json
import os
import pytest
from app.schemas.analytics import BlockConfig, CalculationResult, ReportFilter
from app.services.analytics import evaluate_block
from app.services.ingestion import parse_and_profile_csv

def test_metrics_sum_avg_min_max_count_basic():
    # Simple clean rows
    rows = [
        {"typed": {"val": 10.0}, "structurally_valid": True},
        {"typed": {"val": 20.0}, "structurally_valid": True},
        {"typed": {"val": 30.0}, "structurally_valid": True},
        {"typed": {"val": 40.0}, "structurally_valid": True},
    ]

    res_sum = evaluate_block(rows, BlockConfig(kind="metric", column="val", op="SUM"))
    assert res_sum.primary_value == 100.0
    assert res_sum.row_accounting.included == 4
    assert res_sum.row_accounting.total_rows == 4

    res_avg = evaluate_block(rows, BlockConfig(kind="metric", column="val", op="AVG"))
    assert res_avg.primary_value == 25.0

    res_min = evaluate_block(rows, BlockConfig(kind="metric", column="val", op="MIN"))
    assert res_min.primary_value == 10.0

    res_max = evaluate_block(rows, BlockConfig(kind="metric", column="val", op="MAX"))
    assert res_max.primary_value == 40.0

    res_cnt = evaluate_block(rows, BlockConfig(kind="metric", column="val", op="COUNT"))
    assert res_cnt.primary_value == 4

def test_metrics_negative_values():
    rows = [
        {"typed": {"val": -50.0}, "structurally_valid": True},
        {"typed": {"val": 100.0}, "structurally_valid": True},
        {"typed": {"val": -25.5}, "structurally_valid": True},
    ]

    res_sum = evaluate_block(rows, BlockConfig(kind="metric", column="val", op="SUM"))
    assert res_sum.primary_value == 24.5

    res_min = evaluate_block(rows, BlockConfig(kind="metric", column="val", op="MIN"))
    assert res_min.primary_value == -50.0

    res_max = evaluate_block(rows, BlockConfig(kind="metric", column="val", op="MAX"))
    assert res_max.primary_value == 100.0

def test_metrics_null_and_invalid_handling():
    rows = [
        {"typed": {"val": 10.0}, "structurally_valid": True},
        {"typed": {"val": None}, "structurally_valid": True},     # null
        {"typed": {"val": "invalid"}, "structurally_valid": True}, # non-numeric
        {"typed": {"val": 30.0}, "structurally_valid": True},
        {"typed": {}, "structurally_valid": False},               # structurally invalid
    ]

    res_sum = evaluate_block(rows, BlockConfig(kind="metric", column="val", op="SUM"))
    assert res_sum.primary_value == 40.0
    assert res_sum.row_accounting.total_rows == 5
    assert res_sum.row_accounting.structurally_rejected == 1
    assert res_sum.row_accounting.invalid_for_operation == 2  # None and "invalid"
    assert res_sum.row_accounting.included == 2
    assert res_sum.row_accounting.filtered_out == 0

def test_metrics_empty_selection_deterministic_nulls():
    # When no rows are eligible, MIN, MAX, AVG return None (not misleading zero)
    rows = [
        {"typed": {"val": None}, "structurally_valid": True},
    ]

    res_min = evaluate_block(rows, BlockConfig(kind="metric", column="val", op="MIN"))
    assert res_min.primary_value is None
    assert res_min.formatted_value == "N/A"

    res_max = evaluate_block(rows, BlockConfig(kind="metric", column="val", op="MAX"))
    assert res_max.primary_value is None
    assert res_max.formatted_value == "N/A"

    res_avg = evaluate_block(rows, BlockConfig(kind="metric", column="val", op="AVG"))
    assert res_avg.primary_value is None
    assert res_avg.formatted_value == "N/A"

    # COUNT returns 0
    res_cnt = evaluate_block(rows, BlockConfig(kind="metric", column="val", op="COUNT"))
    assert res_cnt.primary_value == 0
    assert res_cnt.formatted_value == "0"

def test_metrics_count_column_vs_count_rows():
    rows = [
        {"typed": {"val": 10.0}, "structurally_valid": True},
        {"typed": {"val": None}, "structurally_valid": True},
        {"typed": {"val": 30.0}, "structurally_valid": True},
    ]

    # count_non_null (default) should count 2
    res_col = evaluate_block(rows, BlockConfig(kind="metric", column="val", op="COUNT", count_mode="count_non_null"))
    assert res_col.primary_value == 2
    assert res_col.row_accounting.invalid_for_operation == 1
    assert res_col.row_accounting.included == 2

    # count_rows counts all eligible rows (3)
    res_rows = evaluate_block(rows, BlockConfig(kind="metric", column="val", op="COUNT", count_mode="count_rows"))
    assert res_rows.primary_value == 3
    assert res_rows.row_accounting.invalid_for_operation == 0
    assert res_rows.row_accounting.included == 3

def test_metrics_group_by_category():
    rows = [
        {"typed": {"dept": "Eng", "amount": 100.0}, "structurally_valid": True},
        {"typed": {"dept": "Eng", "amount": 200.0}, "structurally_valid": True},
        {"typed": {"dept": "Sales", "amount": 300.0}, "structurally_valid": True},
        {"typed": {"dept": "", "amount": 400.0}, "structurally_valid": True}, # blank dept
    ]

    res = evaluate_block(rows, BlockConfig(kind="metric", column="amount", op="SUM", group_by_column="dept"))
    assert res.row_accounting.total_rows == 4
    assert res.row_accounting.invalid_for_operation == 1 # blank dept
    assert res.row_accounting.included == 3

    # Group breakdown check
    assert res.group_breakdown is not None
    groups = {g.group_key: g for g in res.group_breakdown}
    assert "Eng" in groups
    assert groups["Eng"].value == 300.0
    assert groups["Eng"].included_count == 2
    assert "Sales" in groups
    assert groups["Sales"].value == 300.0
    assert groups["Sales"].included_count == 1

    # Invariant: sum of group included_counts must equal block included count
    assert sum(g.included_count for g in res.group_breakdown) == res.row_accounting.included

def test_metrics_against_synthetic_messy_fixture():
    fixture_csv = os.path.join(os.path.dirname(__file__), "..", "fixtures", "messy_sample.csv")
    expected_json = os.path.join(os.path.dirname(__file__), "..", "fixtures", "expected_results.json")

    with open(fixture_csv, "r", encoding="utf-8") as f:
        csv_text = f.read()
    with open(expected_json, "r", encoding="utf-8") as f:
        expected = json.load(f)["aggregations"]

    _, _, processed_rows = parse_and_profile_csv(csv_text)
    raw_rows = [{"typed": r["typed_json"], "structurally_valid": r["structurally_valid"]} for r in processed_rows]

    # 1. SUM
    res_sum = evaluate_block(raw_rows, BlockConfig(kind="metric", column="amount", op="SUM"))
    assert res_sum.primary_value == expected["amount"]["sum"]
    assert res_sum.row_accounting.model_dump() == expected["amount"]["accounting"]

    # 2. AVG
    res_avg = evaluate_block(raw_rows, BlockConfig(kind="metric", column="amount", op="AVG"))
    assert res_avg.primary_value == expected["amount"]["avg"]

    # 3. MIN
    res_min = evaluate_block(raw_rows, BlockConfig(kind="metric", column="amount", op="MIN"))
    assert res_min.primary_value == expected["amount"]["min"]

    # 4. MAX
    res_max = evaluate_block(raw_rows, BlockConfig(kind="metric", column="amount", op="MAX"))
    assert res_max.primary_value == expected["amount"]["max"]

    # 5. COUNT
    res_cnt = evaluate_block(raw_rows, BlockConfig(kind="metric", column="amount", op="COUNT"))
    assert res_cnt.primary_value == expected["amount"]["count_non_null"]

    # 6. Grouped Bar Chart
    res_bar = evaluate_block(raw_rows, BlockConfig(kind="bar_chart", column="amount", group_by_column="department", op="SUM"))
    assert res_bar.row_accounting.included == expected["department_grouped_sum"]["included_total"]
    group_dict = {g.group_key: g.value for g in res_bar.group_breakdown}
    assert group_dict == expected["department_grouped_sum"]["values"]
    assert sum(g.included_count for g in res_bar.group_breakdown) == res_bar.row_accounting.included

def test_provenance_ast_and_narrative():
    rows = [
        {"typed": {"amount": 100.0}, "structurally_valid": True},
        {"typed": {"amount": None}, "structurally_valid": True},
        {"typed": {}, "structurally_valid": False},
    ]

    res = evaluate_block(rows, BlockConfig(kind="metric", column="amount", op="SUM"))

    # Canonical AST inspection
    ast = res.canonical_ast
    assert ast.operation == "METRIC:SUM"
    assert ast.target_column == "amount"
    assert ast.execution_engine == "polars"
    assert "df.select(pl.col('amount').sum())" in ast.polars_expression

    # Narrative inspection
    narrative = res.narrative_explanation
    assert "Computed SUM of 'amount' using Polars" in narrative
    assert "Included 1" in narrative
    assert "1 structurally invalid/ragged rows" in narrative
    assert "1 rows with null or invalid values" in narrative
