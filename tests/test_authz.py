import pytest
from app.config import settings
from app.db import SessionRecord

def test_health_check(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"

def test_login_success(client, test_users):
    response = client.post(
        "/login",
        data={"email": "user_a@test.com", "password": "PasswordA123!"},
        follow_redirects=False
    )
    assert response.status_code == 303
    assert settings.SESSION_COOKIE_NAME in response.cookies
    cookie = response.cookies[settings.SESSION_COOKIE_NAME]
    assert len(cookie) > 20

def test_login_invalid_password(client, test_users):
    response = client.post(
        "/login",
        data={"email": "user_a@test.com", "password": "WrongPassword!"},
        follow_redirects=False
    )
    assert response.status_code == 400
    assert "Invalid email or password" in response.text
    assert settings.SESSION_COOKIE_NAME not in response.cookies

def test_login_unknown_email(client, test_users):
    response = client.post(
        "/login",
        data={"email": "nonexistent@test.com", "password": "Password123!"},
        follow_redirects=False
    )
    assert response.status_code == 400
    assert "Invalid email or password" in response.text

def test_unauthenticated_access_denied(client):
    response = client.get("/datasets/api")
    assert response.status_code == 401
    assert response.json()["detail"] == "Authentication required"

    response = client.get("/reports/api")
    assert response.status_code == 401

def test_owner_can_access_own_dataset_and_report(auth_client_a, test_users):
    client, _, _ = auth_client_a
    dataset_a = test_users["dataset_a"]
    report_a = test_users["report_a"]

    # Access own dataset
    res_ds = client.get(f"/datasets/{dataset_a.id}/api")
    assert res_ds.status_code == 200
    assert res_ds.json()["id"] == dataset_a.id
    assert res_ds.json()["name"] == dataset_a.name

    # Access own report
    res_rp = client.get(f"/reports/{report_a.id}/api")
    assert res_rp.status_code == 200
    assert res_rp.json()["id"] == report_a.id
    assert res_rp.json()["title"] == report_a.title

def test_cross_tenant_dataset_idor_rejected(auth_client_a, test_users):
    client, _, _ = auth_client_a
    dataset_b = test_users["dataset_b"]

    # User A tries to access User B's dataset
    response = client.get(f"/datasets/{dataset_b.id}/api")
    # Must return 404 to avoid leaking existence
    assert response.status_code == 404
    assert response.json()["detail"] == "Dataset not found"

def test_cross_tenant_report_idor_rejected(auth_client_a, test_users):
    client, _, _ = auth_client_a
    report_b = test_users["report_b"]

    # User A tries to access User B's report
    response = client.get(f"/reports/{report_b.id}/api")
    # Must return 404 to avoid leaking existence
    assert response.status_code == 404
    assert response.json()["detail"] == "Report not found"

def test_dataset_list_only_returns_own_records(auth_client_a, test_users):
    client, _, _ = auth_client_a
    response = client.get("/datasets/api")
    assert response.status_code == 200
    items = response.json()
    assert len(items) == 1
    assert items[0]["id"] == test_users["dataset_a"].id
    # Assert User B's dataset is NOT in the list
    assert not any(item["id"] == test_users["dataset_b"].id for item in items)

def test_report_list_only_returns_own_records(auth_client_a, test_users):
    client, _, _ = auth_client_a
    response = client.get("/reports/api")
    assert response.status_code == 200
    items = response.json()
    assert len(items) == 1
    assert items[0]["id"] == test_users["report_a"].id
    # Assert User B's report is NOT in the list
    assert not any(item["id"] == test_users["report_b"].id for item in items)

def test_csrf_protection_on_logout(auth_client_a):
    client, token, session_record = auth_client_a

    # POST logout with missing CSRF
    client.headers.pop("X-CSRF-Token", None)
    res_no_csrf = client.post("/logout")
    assert res_no_csrf.status_code == 403
    assert "CSRF token" in res_no_csrf.json()["detail"]

    # POST logout with forged/wrong CSRF
    client.headers.update({"X-CSRF-Token": "forged_csrf_token_value"})
    res_bad_csrf = client.post("/logout")
    assert res_bad_csrf.status_code == 403

    # POST logout with valid CSRF in header
    client.headers.update({"X-CSRF-Token": session_record.csrf_token})
    res_valid = client.post("/logout", follow_redirects=False)
    assert res_valid.status_code == 303
    assert res_valid.headers.get("location") == "/login"

    # Verify session is deleted and cannot be reused
    res_after = client.get("/datasets/api")
    assert res_after.status_code == 401

def test_security_headers_present(auth_client_a):
    client, _, _ = auth_client_a
    response = client.get("/datasets/api")
    assert response.headers.get("X-Content-Type-Options") == "nosniff"
    assert response.headers.get("X-Frame-Options") == "DENY"
    assert response.headers.get("Referrer-Policy") == "no-referrer"
    assert "no-store" in response.headers.get("Cache-Control", "")
