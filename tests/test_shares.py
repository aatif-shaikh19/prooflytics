import hashlib
import json
from datetime import datetime, timedelta
import pytest
from app.db.models import Dataset, DatasetRow, Report, ReportBlock, ShareLink
from app.services.shares import create_share_link, hash_token, revoke_share_link

def test_owner_can_create_share_link(auth_client_a, db_session, test_users):
    client_a, _, session_a = auth_client_a
    report_a = test_users["report_a"]

    response = client_a.post(
        f"/reports/{report_a.id}/shares",
        data={
            "csrf_token": session_a.csrf_token,
            "expires_days": 7,
        },
        follow_redirects=False,
    )
    assert response.status_code == 303
    redirect_url = response.headers["location"]
    assert "created_token=" in redirect_url

    raw_token = redirect_url.split("created_token=")[1].split("#")[0]
    expected_hash = hashlib.sha256(raw_token.encode("utf-8")).hexdigest()

    # Verify ShareLink stored in DB has hash matching token
    share_link = (
        db_session.query(ShareLink)
        .filter(ShareLink.report_id == report_a.id)
        .first()
    )
    assert share_link is not None
    assert share_link.token_hash == expected_hash
    assert share_link.revoked_at is None
    assert share_link.expires_at > datetime.utcnow()

    # Negative check: raw token is NEVER stored directly in the database
    raw_in_db = (
        db_session.query(ShareLink)
        .filter(ShareLink.token_hash == raw_token)
        .first()
    )
    assert raw_in_db is None

def test_cross_tenant_cannot_create_or_revoke_share(auth_client_b, db_session, test_users):
    client_b, _, session_b = auth_client_b
    report_a = test_users["report_a"]

    # User B attempting to create share for User A's report -> 404
    res_create = client_b.post(
        f"/reports/{report_a.id}/shares",
        data={
            "csrf_token": session_b.csrf_token,
            "expires_days": 7,
        },
    )
    assert res_create.status_code == 404

    # Create legitimate share for report_a by User A
    share_link, _ = create_share_link(db_session, test_users["user_a"].id, report_a.id)

    # User B attempting to revoke User A's share link -> 404
    res_revoke = client_b.post(
        f"/reports/{report_a.id}/shares/{share_link.id}/revoke",
        data={"csrf_token": session_b.csrf_token},
    )
    assert res_revoke.status_code == 404

def test_anonymous_valid_view_and_provenance(client, db_session, test_users):
    report_a = test_users["report_a"]
    dataset_a = test_users["dataset_a"]

    # Populate rows for calculation
    drow = DatasetRow(
        dataset_id=dataset_a.id,
        source_row_number=1,
        raw_json='{"sales": 500, "category": "Tech"}',
        typed_json='{"sales": 500, "category": "Tech"}',
        structurally_valid=True,
    )
    db_session.add(drow)

    # Add block
    block = ReportBlock(
        report_id=report_a.id,
        kind="metric",
        position=0,
        config_json=json.dumps({"column": "sales", "op": "SUM", "title": "Total Sales KPI"}),
    )
    db_session.add(block)
    db_session.commit()

    # Generate share link
    share_link, raw_token = create_share_link(
        db_session, test_users["user_a"].id, report_a.id, expires_in_days=7
    )

    # Anonymous unauthenticated client views shared report
    res_html = client.get(f"/share/{raw_token}")
    assert res_html.status_code == 200
    assert report_a.title in res_html.text
    assert "Total Sales KPI" in res_html.text
    assert "500" in res_html.text
    assert "How was this calculated?" in res_html.text
    assert "CANONICAL EXECUTED AST (POLARS)" in res_html.text

    # Security headers
    assert "no-store" in res_html.headers.get("Cache-Control", "")
    assert res_html.headers.get("Referrer-Policy") == "no-referrer"

    # Leakage checks: no edit controls or raw dataset access
    assert "Delete Report" not in res_html.text
    assert "+ Add Report Block" not in res_html.text
    assert "Back to Dashboard" not in res_html.text
    assert f"/datasets/{dataset_a.id}" not in res_html.text

    # Anonymous JSON API projection
    res_api = client.get(f"/share/{raw_token}/api")
    assert res_api.status_code == 200
    api_data = res_api.json()
    assert api_data["report_title"] == report_a.title
    assert len(api_data["blocks"]) == 1
    assert api_data["blocks"][0]["calculation"]["primary_value"] == 500

    # API does NOT leak dataset ID, owner ID, or user email
    assert "dataset_id" not in api_data
    assert "owner_id" not in api_data
    assert "user_a@test.com" not in str(api_data)

def test_revoked_share_link_denial(client, auth_client_a, db_session, test_users):
    client_a, _, session_a = auth_client_a
    report_a = test_users["report_a"]

    share_link, raw_token = create_share_link(
        db_session, test_users["user_a"].id, report_a.id
    )

    # Active view works
    assert client.get(f"/share/{raw_token}").status_code == 200

    # Owner revokes
    revoke_res = client_a.post(
        f"/reports/{report_a.id}/shares/{share_link.id}/revoke",
        data={"csrf_token": session_a.csrf_token},
        follow_redirects=False,
    )
    assert revoke_res.status_code == 303

    # Subsequent anonymous request is denied with 410 Gone
    res_revoked = client.get(f"/share/{raw_token}")
    assert res_revoked.status_code == 410
    assert "Share Link Revoked" in res_revoked.text
    assert "revoked by the report owner" in res_revoked.text

    # API also returns 410 Gone
    res_api_revoked = client.get(f"/share/{raw_token}/api")
    assert res_api_revoked.status_code == 410

def test_expired_share_link_denial(client, db_session, test_users):
    report_a = test_users["report_a"]

    share_link, raw_token = create_share_link(
        db_session, test_users["user_a"].id, report_a.id
    )

    # Backdate expiration to 1 day ago
    share_link.expires_at = datetime.utcnow() - timedelta(days=1)
    db_session.commit()

    # Anonymous request to expired link is denied with 410 Gone
    res_expired = client.get(f"/share/{raw_token}")
    assert res_expired.status_code == 410
    assert "Share Link Expired" in res_expired.text
    assert "expired and is no longer accessible" in res_expired.text

    # API also returns 410 Gone
    res_api_expired = client.get(f"/share/{raw_token}/api")
    assert res_api_expired.status_code == 410

def test_tampered_and_nonexistent_token(client):
    # Completely fake token -> 404 Not Found
    res = client.get("/share/completely_nonexistent_token_1234567890")
    assert res.status_code == 404
    assert "Report Not Found" in res.text

    res_api = client.get("/share/completely_nonexistent_token_1234567890/api")
    assert res_api.status_code == 404

def test_anonymous_cannot_access_private_endpoints(client, test_users):
    report_a = test_users["report_a"]
    dataset_a = test_users["dataset_a"]

    # All private endpoints reject unauthenticated calls
    assert client.get(f"/reports/{report_a.id}").status_code == 401
    assert client.get(f"/reports/{report_a.id}/api").status_code == 401
    assert client.get(f"/datasets/{dataset_a.id}").status_code == 401
    assert client.get(f"/datasets/{dataset_a.id}/api").status_code == 401
    assert client.get("/reports/api").status_code == 401
    assert client.get("/datasets/api").status_code == 401
    assert client.post(f"/reports/{report_a.id}/blocks").status_code == 401
    assert client.post(f"/reports/{report_a.id}/delete").status_code == 401

def test_live_report_semantics(client, auth_client_a, db_session, test_users):
    client_a, _, session_a = auth_client_a
    report_a = test_users["report_a"]
    dataset_a = test_users["dataset_a"]

    # Populate rows
    db_session.add_all([
        DatasetRow(
            dataset_id=dataset_a.id,
            source_row_number=1,
            raw_json='{"sales": 100, "category": "A"}',
            typed_json='{"sales": 100, "category": "A"}',
            structurally_valid=True,
        ),
        DatasetRow(
            dataset_id=dataset_a.id,
            source_row_number=2,
            raw_json='{"sales": 200, "category": "B"}',
            typed_json='{"sales": 200, "category": "B"}',
            structurally_valid=True,
        ),
    ])
    db_session.commit()

    # Initial metric block
    block = ReportBlock(
        report_id=report_a.id,
        kind="metric",
        position=0,
        config_json=json.dumps({"column": "sales", "op": "SUM", "title": "Live Revenue"}),
    )
    db_session.add(block)
    db_session.commit()

    # Generate share link
    _, raw_token = create_share_link(
        db_session, test_users["user_a"].id, report_a.id
    )

    # Initial shared view shows SUM = 300
    res_1 = client.get(f"/share/{raw_token}")
    assert res_1.status_code == 200
    assert "300" in res_1.text

    # Owner adds a filter (only category "A")
    client_a.post(
        f"/reports/{report_a.id}/filter",
        data={
            "csrf_token": session_a.csrf_token,
            "category_column": "category",
            "selected_categories": "A",
        },
    )

    # Live share automatically reflects updated calculation: SUM = 100
    res_2 = client.get(f"/share/{raw_token}")
    assert res_2.status_code == 200
    assert "100" in res_2.text
