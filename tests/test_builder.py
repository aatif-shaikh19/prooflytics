import json
import pytest
from app.db.models import Dataset, DatasetRow, Report, ReportBlock
from app.services.reports import evaluate_report_blocks

def test_report_create_page(auth_client_a, test_users):
    client, _, _ = auth_client_a
    response = client.get("/reports/create")
    assert response.status_code == 200
    assert "Create New Report" in response.text
    # User A dataset should appear
    assert test_users["dataset_a"].name in response.text
    # User B dataset must NOT appear
    assert test_users["dataset_b"].name not in response.text

def test_report_create_post(auth_client_a, db_session, test_users):
    client, _, session_rec = auth_client_a
    dataset_a = test_users["dataset_a"]

    # Valid report creation
    response = client.post(
        "/reports",
        data={
            "csrf_token": session_rec.csrf_token,
            "title": "Quarterly Performance",
            "dataset_id": dataset_a.id,
        },
        follow_redirects=False,
    )
    assert response.status_code == 303
    redirect_url = response.headers["location"]
    assert redirect_url.startswith("/reports/")

    report_id = redirect_url.split("/")[-1]
    created = db_session.query(Report).filter(Report.id == report_id).first()
    assert created is not None
    assert created.title == "Quarterly Performance"
    assert created.owner_id == test_users["user_a"].id

def test_report_create_cross_tenant_forbidden(auth_client_a, test_users):
    client, _, session_rec = auth_client_a
    dataset_b = test_users["dataset_b"]

    # User A attempting to create report for User B's dataset
    response = client.post(
        "/reports",
        data={
            "csrf_token": session_rec.csrf_token,
            "title": "Stealing B's data",
            "dataset_id": dataset_b.id,
        },
    )
    # Must reject with 404
    assert response.status_code == 404

def test_report_view_and_cross_tenant(auth_client_a, auth_client_b, test_users):
    client_a, _, _ = auth_client_a
    client_b, _, _ = auth_client_b
    report_a = test_users["report_a"]

    # Owner can view
    res_a = client_a.get(f"/reports/{report_a.id}")
    assert res_a.status_code == 200
    assert report_a.title in res_a.text

    # Cross tenant User B gets 404
    res_b = client_b.get(f"/reports/{report_a.id}")
    assert res_b.status_code == 404

def test_report_title_edit(auth_client_a, auth_client_b, db_session, test_users):
    client_a, _, session_a = auth_client_a
    client_b, _, session_b = auth_client_b
    report_a = test_users["report_a"]

    # Owner edits title
    res_a = client_a.post(
        f"/reports/{report_a.id}/edit",
        data={
            "csrf_token": session_a.csrf_token,
            "title": "Renamed Report A",
        },
        follow_redirects=False,
    )
    assert res_a.status_code == 303
    db_session.refresh(report_a)
    assert report_a.title == "Renamed Report A"

    # User B cannot edit User A's report
    res_b = client_b.post(
        f"/reports/{report_a.id}/edit",
        data={
            "csrf_token": session_b.csrf_token,
            "title": "Hacked Title",
        },
    )
    assert res_b.status_code == 404
    db_session.refresh(report_a)
    assert report_a.title == "Renamed Report A"

def test_report_filter_update_and_clear(auth_client_a, db_session, test_users):
    client_a, _, session_a = auth_client_a
    report_a = test_users["report_a"]

    # Apply filter
    res = client_a.post(
        f"/reports/{report_a.id}/filter",
        data={
            "csrf_token": session_a.csrf_token,
            "date_column": "order_date",
            "start_date": "2024-01-01",
            "end_date": "2024-06-30",
            "category_column": "region",
            "selected_categories": "North, South",
        },
        follow_redirects=False,
    )
    assert res.status_code == 303
    db_session.refresh(report_a)

    filter_data = json.loads(report_a.filter_json)
    assert filter_data["date_column"] == "order_date"
    assert filter_data["start_date"] == "2024-01-01"
    assert filter_data["end_date"] == "2024-06-30"
    assert filter_data["category_column"] == "region"
    assert filter_data["selected_categories"] == ["North", "South"]

    # Clear filter
    res_clear = client_a.post(
        f"/reports/{report_a.id}/filter",
        data={
            "csrf_token": session_a.csrf_token,
            "clear": "true",
        },
        follow_redirects=False,
    )
    assert res_clear.status_code == 303
    db_session.refresh(report_a)
    cleared_filter = json.loads(report_a.filter_json)
    assert cleared_filter.get("date_column") is None
    assert cleared_filter.get("selected_categories") is None

def test_block_crud_all_kinds(auth_client_a, db_session, test_users):
    client_a, _, session_a = auth_client_a
    report_a = test_users["report_a"]

    kinds = [
        ("metric", {"column": "revenue", "op": "SUM", "title": "Total Revenue"}),
        ("bar_chart", {"column": "revenue", "group_by_column": "dept", "title": "Dept Revenue"}),
        ("line_chart", {"column": "revenue", "group_by_column": "date", "title": "Revenue Over Time"}),
        ("top_n_table", {"column": "revenue", "limit": 5, "title": "Top Deals"}),
        ("note", {"note_text": "This is an explanatory note.", "title": "Executive Context"}),
    ]

    for kind, extra in kinds:
        data = {
            "csrf_token": session_a.csrf_token,
            "kind": kind,
            **extra,
        }
        res = client_a.post(
            f"/reports/{report_a.id}/blocks",
            data=data,
            follow_redirects=False,
        )
        assert res.status_code == 303

    # Check that all 5 blocks were created with sequential positions 0, 1, 2, 3, 4
    blocks = (
        db_session.query(ReportBlock)
        .filter(ReportBlock.report_id == report_a.id)
        .order_by(ReportBlock.position.asc())
        .all()
    )
    assert len(blocks) == 5
    for idx, b in enumerate(blocks):
        assert b.position == idx
        assert b.kind == kinds[idx][0]

    # Delete block at position 1 (bar_chart)
    del_block_id = blocks[1].id
    res_del = client_a.post(
        f"/reports/{report_a.id}/blocks/{del_block_id}/delete",
        data={"csrf_token": session_a.csrf_token},
        follow_redirects=False,
    )
    assert res_del.status_code == 303

    # Check remaining blocks positions re-normalized to 0, 1, 2, 3
    remaining = (
        db_session.query(ReportBlock)
        .filter(ReportBlock.report_id == report_a.id)
        .order_by(ReportBlock.position.asc())
        .all()
    )
    assert len(remaining) == 4
    for idx, b in enumerate(remaining):
        assert b.position == idx

def test_block_reorder_keyboard_accessible(auth_client_a, db_session, test_users):
    client_a, _, session_a = auth_client_a
    report_a = test_users["report_a"]

    # Clear any prior blocks
    db_session.query(ReportBlock).filter(ReportBlock.report_id == report_a.id).delete()
    db_session.commit()

    # Add 3 blocks
    b0 = ReportBlock(report_id=report_a.id, kind="metric", position=0, config_json='{"title": "B0"}')
    b1 = ReportBlock(report_id=report_a.id, kind="note", position=1, config_json='{"title": "B1"}')
    b2 = ReportBlock(report_id=report_a.id, kind="top_n_table", position=2, config_json='{"title": "B2"}')
    db_session.add_all([b0, b1, b2])
    db_session.commit()

    # Move b1 UP -> should swap with b0
    res_up = client_a.post(
        f"/reports/{report_a.id}/blocks/{b1.id}/move",
        data={"csrf_token": session_a.csrf_token, "direction": "up"},
        follow_redirects=False,
    )
    assert res_up.status_code == 303
    db_session.refresh(b0)
    db_session.refresh(b1)
    db_session.refresh(b2)
    assert b1.position == 0
    assert b0.position == 1
    assert b2.position == 2

    # Move b1 DOWN -> should swap back with b0
    res_down = client_a.post(
        f"/reports/{report_a.id}/blocks/{b1.id}/move",
        data={"csrf_token": session_a.csrf_token, "direction": "down"},
        follow_redirects=False,
    )
    assert res_down.status_code == 303
    db_session.refresh(b0)
    db_session.refresh(b1)
    db_session.refresh(b2)
    assert b0.position == 0
    assert b1.position == 1
    assert b2.position == 2

    # Move b0 UP (already at boundary) -> no change
    res_boundary = client_a.post(
        f"/reports/{report_a.id}/blocks/{b0.id}/move",
        data={"csrf_token": session_a.csrf_token, "direction": "up"},
        follow_redirects=False,
    )
    assert res_boundary.status_code == 303
    db_session.refresh(b0)
    assert b0.position == 0

def test_report_delete_cascades_blocks(auth_client_a, db_session, test_users):
    client_a, _, session_a = auth_client_a
    report_a = test_users["report_a"]

    # Ensure a block exists
    block = ReportBlock(report_id=report_a.id, kind="note", position=0, config_json='{}')
    db_session.add(block)
    db_session.commit()

    res = client_a.post(
        f"/reports/{report_a.id}/delete",
        data={"csrf_token": session_a.csrf_token},
        follow_redirects=False,
    )
    assert res.status_code == 303
    assert res.headers["location"] == "/"

    # Report and block should be gone
    assert db_session.query(Report).filter(Report.id == report_a.id).first() is None
    assert db_session.query(ReportBlock).filter(ReportBlock.report_id == report_a.id).first() is None

def test_report_evaluation_and_provenance_modal(auth_client_a, db_session, test_users):
    client_a, _, session_a = auth_client_a
    dataset_a = test_users["dataset_a"]

    # Populate dataset with schema and rows
    dataset_a.schema_json = json.dumps({
        "columns": [
            {"name": "sales", "type": "number"},
            {"name": "category", "type": "category"},
            {"name": "tx_date", "type": "date"},
        ]
    })
    db_session.commit()

    rows = [
        {"sales": 100, "category": "Electronics", "tx_date": "2024-01-10"},
        {"sales": 200, "category": "Furniture", "tx_date": "2024-02-15"},
        {"sales": 300, "category": "Electronics", "tx_date": "2024-03-20"},
        {"sales": None, "category": "Electronics", "tx_date": "2024-04-01"},
    ]
    for idx, r in enumerate(rows, 1):
        drow = DatasetRow(
            dataset_id=dataset_a.id,
            source_row_number=idx,
            raw_json=json.dumps(r),
            typed_json=json.dumps(r),
            structurally_valid=True,
        )
        db_session.add(drow)
    db_session.commit()

    # Create report with a SUM metric block
    report = Report(
        owner_id=test_users["user_a"].id,
        dataset_id=dataset_a.id,
        title="Revenue Analysis",
        filter_json="{}",
    )
    db_session.add(report)
    db_session.commit()

    block = ReportBlock(
        report_id=report.id,
        kind="metric",
        position=0,
        config_json=json.dumps({"column": "sales", "op": "SUM", "title": "Total Sales"}),
    )
    db_session.add(block)
    db_session.commit()

    # 1. View report page
    res = client_a.get(f"/reports/{report.id}")
    assert res.status_code == 200
    assert "Revenue Analysis" in res.text
    # Sum of 100 + 200 + 300 = 600
    assert "600" in res.text
    assert "How was this calculated?" in res.text
    assert "CANONICAL EXECUTED AST (POLARS)" in res.text
    assert "ROW ACCOUNTING RECONCILIATION" in res.text

    # 2. Apply category filter: only "Electronics"
    res_filt = client_a.post(
        f"/reports/{report.id}/filter",
        data={
            "csrf_token": session_a.csrf_token,
            "category_column": "category",
            "selected_categories": "Electronics",
        },
        follow_redirects=True,
    )
    assert res_filt.status_code == 200
    # Sum of Electronics: 100 + 300 = 400 (Furniture 200 is filtered out)
    assert "400" in res_filt.text

def test_reports_api_isolation(auth_client_a, auth_client_b, test_users):
    client_a, _, _ = auth_client_a
    client_b, _, _ = auth_client_b
    report_a = test_users["report_a"]

    # User A API list
    res_a = client_a.get("/reports/api")
    assert res_a.status_code == 200
    data_a = res_a.json()
    assert any(r["id"] == report_a.id for r in data_a)

    # User B API list should NOT include User A's report
    res_b = client_b.get("/reports/api")
    assert res_b.status_code == 200
    data_b = res_b.json()
    assert not any(r["id"] == report_a.id for r in data_b)

    # Single report API
    res_single_a = client_a.get(f"/reports/{report_a.id}/api")
    assert res_single_a.status_code == 200
    assert res_single_a.json()["id"] == report_a.id

    res_single_b = client_b.get(f"/reports/{report_a.id}/api")
    assert res_single_b.status_code == 404
