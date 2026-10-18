import json
import pytest
from app.db.models import Dataset, Report, ReportBlock
from app.services.suggestions import get_deterministic_suggestions

def test_deterministic_suggestions_rules(db_session, test_users):
    user_a = test_users["user_a"]

    # 1. Dataset with number, category, date
    ds_full = Dataset(
        owner_id=user_a.id,
        name="Sales Dataset",
        status="ready",
        original_filename="sales.csv",
        row_count=100,
        schema_json=json.dumps({
            "columns": [
                {"name": "revenue", "type": "number"},
                {"name": "region", "type": "category"},
                {"name": "order_date", "type": "date"},
            ]
        }),
    )
    db_session.add(ds_full)
    db_session.flush()

    sugg_full = get_deterministic_suggestions(ds_full)
    kinds = [s["kind"] for s in sugg_full]
    assert "metric" in kinds
    assert "bar_chart" in kinds
    assert "line_chart" in kinds
    assert "top_n_table" in kinds
    assert "note" in kinds

    # Verify bar chart groups by region and targets revenue
    bar_sugg = next(s for s in sugg_full if s["kind"] == "bar_chart")
    assert bar_sugg["column"] == "revenue"
    assert bar_sugg["group_by_column"] == "region"

    # Verify line chart groups by date and targets revenue
    line_sugg = next(s for s in sugg_full if s["kind"] == "line_chart")
    assert line_sugg["column"] == "revenue"
    assert line_sugg["group_by_column"] == "order_date"

    # 2. Dataset with only category and text (no numbers)
    ds_no_num = Dataset(
        owner_id=user_a.id,
        name="Feedback Dataset",
        status="ready",
        original_filename="feedback.csv",
        row_count=50,
        schema_json=json.dumps({
            "columns": [
                {"name": "category", "type": "category"},
                {"name": "comments", "type": "text"},
            ]
        }),
    )
    db_session.add(ds_no_num)
    db_session.commit()

    sugg_no_num = get_deterministic_suggestions(ds_no_num)
    kinds_no_num = [s["kind"] for s in sugg_no_num]
    assert "bar_chart" not in kinds_no_num
    assert "metric" not in kinds_no_num
    assert "note" in kinds_no_num

def test_human_confirmed_report_creation(auth_client_a, db_session, test_users):
    client_a, _, session_a = auth_client_a
    dataset_a = test_users["dataset_a"]

    # Set up schema on dataset_a
    dataset_a.schema_json = json.dumps({
        "columns": [
            {"name": "sales", "type": "number"},
            {"name": "department", "type": "category"},
        ]
    })
    db_session.commit()

    # User clicks "+ Create Report with Suggested Blocks"
    response = client_a.post(
        "/reports/from-suggestions",
        data={
            "csrf_token": session_a.csrf_token,
            "dataset_id": dataset_a.id,
            "title": "Confirmed Suggested Report",
        },
        follow_redirects=False,
    )
    assert response.status_code == 303
    redirect_url = response.headers["location"]
    assert redirect_url.startswith("/reports/")

    report_id = redirect_url.split("/")[-1]
    created_report = db_session.query(Report).filter(Report.id == report_id).first()
    assert created_report is not None
    assert created_report.title == "Confirmed Suggested Report"
    assert created_report.owner_id == test_users["user_a"].id

    # Verify blocks were generated sequentially
    blocks = (
        db_session.query(ReportBlock)
        .filter(ReportBlock.report_id == report_id)
        .order_by(ReportBlock.position.asc())
        .all()
    )
    assert len(blocks) >= 3
    for idx, b in enumerate(blocks):
        assert b.position == idx

def test_suggestions_cross_tenant_rejection(auth_client_b, test_users):
    client_b, _, session_b = auth_client_b
    dataset_a = test_users["dataset_a"]

    # User B attempting to create report from User A's dataset -> 404
    response = client_b.post(
        "/reports/from-suggestions",
        data={
            "csrf_token": session_b.csrf_token,
            "dataset_id": dataset_a.id,
        },
    )
    assert response.status_code == 404

def test_suggestions_with_legacy_string_schema_json(auth_client_a, db_session, test_users):
    client_a, _, _ = auth_client_a
    user_a = test_users["user_a"]

    # Legacy schema where columns is list of strings
    ds_legacy = Dataset(
        owner_id=user_a.id,
        name="Legacy String Schema Dataset",
        status="ready",
        original_filename="legacy.csv",
        row_count=10,
        schema_json='{"columns": ["id", "amount", "category"]}',
        profile_json='{"total_rows": 10, "accepted_rows": 10, "rejected_rows": 0}',
    )
    db_session.add(ds_legacy)
    db_session.commit()

    # Must not raise AttributeError: 'str' object has no attribute 'get'
    suggestions = get_deterministic_suggestions(ds_legacy)
    assert isinstance(suggestions, list)
    assert len(suggestions) > 0  # At least note suggestion

    # GET /datasets/{id} HTML page must return 200 OK
    res = client_a.get(f"/datasets/{ds_legacy.id}")
    assert res.status_code == 200

def test_report_view_with_null_target_column_no_crash(auth_client_a, db_session, test_users):
    client_a, _, _ = auth_client_a
    user_a = test_users["user_a"]
    dataset_a = test_users["dataset_a"]

    # Report with a block where column is None
    report = Report(
        owner_id=user_a.id,
        dataset_id=dataset_a.id,
        title="Null Column Report",
        filter_json="{}",
    )
    db_session.add(report)
    db_session.commit()

    b1 = ReportBlock(
        report_id=report.id,
        kind="metric",
        position=0,
        config_json=json.dumps({"title": "Unconfigured Metric", "op": "SUM", "column": None}),
    )
    b2 = ReportBlock(
        report_id=report.id,
        kind="bar_chart",
        position=1,
        config_json=json.dumps({"title": "Unconfigured Bar", "op": "SUM", "column": None, "group_by_column": None}),
    )
    db_session.add_all([b1, b2])
    db_session.commit()

    # GET /reports/{id} HTML page must return 200 OK and not crash Polars with TypeError
    res = client_a.get(f"/reports/{report.id}")
    assert res.status_code == 200
    assert "Unconfigured Metric" in res.text

