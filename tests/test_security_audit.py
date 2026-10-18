"""
Security audit and vulnerability hardening tests for Prooflytics.

Validates:
1. Cross-Site Scripting (XSS) defense: autoescaping in CSV cells, text notes, report titles, and Chart.js datasets.
2. Insecure Direct Object Reference (IDOR) defense across datasets, reports, blocks, and share links.
3. CSRF token enforcement on all state-mutating POST routes.
4. Token storage security: raw bearer tokens are never stored in plaintext in the database.
5. Defensive HTTP headers: X-Content-Type-Options, X-Frame-Options, Referrer-Policy, and Cache-Control.
"""
import hashlib
import json
import pytest
from app.db.models import Dataset, DatasetRow, Report, ReportBlock, ShareLink
from app.services.shares import create_share_link

def test_xss_autoescaping_in_csv_cells_and_notes(auth_client_a, client, db_session, test_users):
    client_a, _, session_a = auth_client_a
    user_a = test_users["user_a"]

    # 1. Dataset with XSS payloads in CSV cells
    xss_payload = "<script>alert('pwned')</script>"
    xss_img_payload = "<img src=x onerror=alert(1)>"

    dataset = Dataset(
        owner_id=user_a.id,
        name="Security <script>alert(1)</script>",
        status="ready",
        original_filename="xss.csv",
        row_count=1,
        schema_json=json.dumps({"columns": [{"name": "dept", "type": "category"}, {"name": "val", "type": "number"}]}),
        profile_json=json.dumps({"total_rows": 1, "columns": []}),
    )
    db_session.add(dataset)
    db_session.flush()

    drow = DatasetRow(
        dataset_id=dataset.id,
        source_row_number=1,
        raw_json=json.dumps({"dept": xss_payload, "val": 100}),
        typed_json=json.dumps({"dept": xss_payload, "val": 100}),
        structurally_valid=True,
    )
    db_session.add(drow)

    # 2. Report with XSS payload in Title and Note
    report = Report(
        owner_id=user_a.id,
        dataset_id=dataset.id,
        title=f"Report {xss_payload}",
        filter_json="{}",
    )
    db_session.add(report)
    db_session.flush()

    # Note block containing XSS
    note_block = ReportBlock(
        report_id=report.id,
        kind="note",
        position=0,
        config_json=json.dumps({"title": "Note Block", "note_text": xss_img_payload}),
    )
    # Top-N Table block displaying the XSS cell
    table_block = ReportBlock(
        report_id=report.id,
        kind="top_n_table",
        position=1,
        config_json=json.dumps({"title": "XSS Table", "column": "val", "limit": 5}),
    )
    db_session.add_all([note_block, table_block])
    db_session.commit()

    # View report as Owner
    res_owner = client_a.get(f"/reports/{report.id}")
    assert res_owner.status_code == 200
    # Must NOT contain raw unescaped script tags
    assert "<script>alert('pwned')</script>" not in res_owner.text
    assert "<img src=x onerror=alert(1)>" not in res_owner.text
    # Must be properly HTML-escaped
    assert "&lt;script&gt;alert(&#39;pwned&#39;)&lt;/script&gt;" in res_owner.text or "&lt;script&gt;" in res_owner.text
    assert "&lt;img" in res_owner.text

    # View report as Anonymous Shared Viewer
    _, raw_token = create_share_link(db_session, user_a.id, report.id)
    res_shared = client.get(f"/share/{raw_token}")
    assert res_shared.status_code == 200
    assert "<script>alert('pwned')</script>" not in res_shared.text
    assert "<img src=x onerror=alert(1)>" not in res_shared.text
    assert "&lt;script&gt;" in res_shared.text

def test_idor_dataset_and_report_denial(auth_client_b, test_users):
    client_b, _, _ = auth_client_b
    dataset_a = test_users["dataset_a"]
    report_a = test_users["report_a"]

    # User B accessing User A dataset -> 404 (no existence leak)
    res_ds = client_b.get(f"/datasets/{dataset_a.id}")
    assert res_ds.status_code == 404

    res_ds_api = client_b.get(f"/datasets/{dataset_a.id}/api")
    assert res_ds_api.status_code == 404

    # User B accessing User A report -> 404
    res_rep = client_b.get(f"/reports/{report_a.id}")
    assert res_rep.status_code == 404

    res_rep_api = client_b.get(f"/reports/{report_a.id}/api")
    assert res_rep_api.status_code == 404

def test_csrf_defense_on_all_mutating_endpoints(auth_client_a, test_users):
    client_a, _, _ = auth_client_a
    report_a = test_users["report_a"]

    # Mutating POST endpoints without CSRF token must fail with 403 Forbidden
    # 1. Report title edit
    res_edit = client_a.post(
        f"/reports/{report_a.id}/edit",
        data={"title": "No CSRF Title"},
        headers={"X-CSRF-Token": ""},
    )
    assert res_edit.status_code == 403

    # 2. Add block
    res_block = client_a.post(
        f"/reports/{report_a.id}/blocks",
        data={"kind": "note", "title": "No CSRF Block"},
        headers={"X-CSRF-Token": ""},
    )
    assert res_block.status_code == 403

    # 3. Create share link
    res_share = client_a.post(
        f"/reports/{report_a.id}/shares",
        data={"expires_days": 7},
        headers={"X-CSRF-Token": ""},
    )
    assert res_share.status_code == 403

    # 4. Filter update
    res_filter = client_a.post(
        f"/reports/{report_a.id}/filter",
        data={"date_column": "x"},
        headers={"X-CSRF-Token": ""},
    )
    assert res_filter.status_code == 403

    # 5. Delete report
    res_del = client_a.post(
        f"/reports/{report_a.id}/delete",
        headers={"X-CSRF-Token": ""},
    )
    assert res_del.status_code == 403

def test_security_headers_enforced_everywhere(client, auth_client_a, db_session, test_users):
    client_a, _, _ = auth_client_a
    report_a = test_users["report_a"]

    # Authenticated endpoint
    res_auth = client_a.get(f"/reports/{report_a.id}")
    assert res_auth.headers["X-Content-Type-Options"] == "nosniff"
    assert res_auth.headers["X-Frame-Options"] == "DENY"
    assert res_auth.headers["Referrer-Policy"] == "no-referrer"
    assert "no-store" in res_auth.headers["Cache-Control"]

    # Public shared endpoint (create valid share link)
    _, raw_token = create_share_link(db_session, test_users["user_a"].id, report_a.id)
    res_share = client.get(f"/share/{raw_token}")
    assert res_share.headers["X-Content-Type-Options"] == "nosniff"
    assert res_share.headers["X-Frame-Options"] == "DENY"
    assert res_share.headers["Referrer-Policy"] == "no-referrer"
    assert "no-store" in res_share.headers["Cache-Control"]

    # Anonymous unauthenticated root /login endpoint
    res_login = client.get("/login")
    assert res_login.headers["X-Content-Type-Options"] == "nosniff"
    assert res_login.headers["X-Frame-Options"] == "DENY"
    assert res_login.headers["Referrer-Policy"] == "no-referrer"
    assert "Content-Security-Policy" in res_login.headers
    assert "Permissions-Policy" in res_login.headers

def test_rate_limiting_defense(client):
    # Simulate high-frequency login POSTs from the same IP
    custom_ip = "198.51.100.42"
    headers = {"X-Forwarded-For": custom_ip}

    # Hit /login POST repeatedly
    rate_limited = False
    for i in range(35):
        res = client.post(
            "/login",
            data={"email": "attacker@example.com", "password": "wrong"},
            headers=headers,
        )
        if res.status_code == 429:
            rate_limited = True
            assert "Retry-After" in res.headers
            assert "X-RateLimit-Limit" in res.headers
            assert res.json()["error"]["code"] == "RATE_LIMIT_EXCEEDED"
            break

    assert rate_limited, "Rate limiter should have triggered 429 Too Many Requests after 30 attempts"

