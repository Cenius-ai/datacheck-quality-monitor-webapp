"""Sign-in, sign-out and the session guard around the app and the API."""

from __future__ import annotations

from datacheck import repositories as repo

DEMO = {"email": "cenius@cenius.ai", "password": "cenius"}


def test_login_page_renders_the_demo_hint(client):
    response = client.get("/login")
    body = response.get_data(as_text=True)
    assert response.status_code == 200
    assert "Datacheck Quality Monitor" in body
    assert "Demo: cenius@cenius.ai / cenius" in body
    # The selectors the auth contract points at must exist in the DOM.
    assert 'name="email"' in body
    assert 'type="password"' in body
    assert 'type="submit"' in body


def test_root_redirects_anonymous_visitors_to_login(client):
    response = client.get("/")
    assert response.status_code == 302
    assert "/login" in response.headers["Location"]


def test_root_redirects_signed_in_users_to_the_workspace(auth_client):
    response = auth_client.get("/")
    assert response.status_code == 302
    assert response.headers["Location"].endswith("/app/")


def test_signin_with_the_demo_account_creates_a_session(auth_client):
    from datacheck.auth import service
    from datacheck.config import SESSION_COOKIE_NAME

    token = auth_client.get_cookie(SESSION_COOKIE_NAME).value
    session = repo.get_session(token)
    assert session is not None
    assert session["email"] == "cenius@cenius.ai"
    assert service.session_user(token) is not None


def test_password_is_hashed_and_verifiable_through_the_login_path():
    from datacheck.auth.passwords import verify_password

    user = repo.get_user_by_email("cenius@cenius.ai")
    assert user["password_hash"] != "cenius"
    assert verify_password(user["password_hash"], "cenius")
    assert not verify_password(user["password_hash"], "wrong-password")


def test_wrong_password_returns_one_generic_message(client):
    response = client.post("/api/auth/signin", json={"email": "cenius@cenius.ai", "password": "nope"})
    assert response.status_code == 401
    payload = response.get_json()
    assert payload["error"]["message"] == "Email or password is incorrect."
    assert payload["error"]["fields"] == {}
    with client.session_transaction() as _session:
        pass
    assert client.get_cookie("datacheck_session") is None


def test_unknown_email_gets_the_same_message(client):
    response = client.post(
        "/api/auth/signin", json={"email": "nobody@example.com", "password": "whatever"}
    )
    assert response.status_code == 401
    assert response.get_json()["error"]["message"] == "Email or password is incorrect."


def test_blank_and_malformed_credentials_are_rejected_per_field(client):
    blank = client.post("/api/auth/signin", json={"email": "", "password": ""})
    assert blank.status_code == 422
    fields = blank.get_json()["error"]["fields"]
    assert "email" in fields and "password" in fields

    malformed = client.post("/api/auth/signin", json={"email": "not-an-email", "password": "x"})
    assert malformed.status_code == 422
    assert "email" in malformed.get_json()["error"]["fields"]

    no_session = client.post("/api/auth/signin", json={"email": "nobody@example.com", "password": ""})
    assert no_session.status_code == 422


def test_signout_clears_the_session(auth_client):
    assert auth_client.get("/api/datasets").status_code == 200
    response = auth_client.post("/api/auth/signout")
    assert response.status_code == 200
    assert auth_client.get("/api/datasets").status_code == 401


def test_anonymous_api_requests_are_rejected(client):
    for path in ("/api/datasets", "/api/datasets/1/runs", "/api/runs/1/rule-results"):
        response = client.get(path)
        assert response.status_code == 401, path
        assert response.get_json()["error"]["code"] == "unauthenticated"


def test_app_shell_redirects_anonymous_visitors_with_the_target_preserved(client):
    response = client.get("/app/?tab=rules")
    assert response.status_code == 302
    location = response.headers["Location"]
    assert location.startswith("/login?next=")
    assert "tab%3Drules" in location


def test_app_shell_is_served_to_signed_in_users(auth_client):
    response = auth_client.get("/app/")
    assert response.status_code == 200
    body = response.get_data(as_text=True)
    assert "Datacheck Quality Monitor" in body
    assert 'id="react-entry-point"' in body


def test_security_headers_are_present(auth_client):
    response = auth_client.get("/app/")
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.headers["X-Frame-Options"] == "DENY"
    assert response.headers["Referrer-Policy"] == "strict-origin-when-cross-origin"
    csp = response.headers["Content-Security-Policy"]
    assert "default-src 'self'" in csp
    assert "script-src 'self'" in csp
    assert "frame-ancestors 'none'" in csp


def test_static_assets_are_served_locally(client):
    css = client.get("/static/style.css")
    assert css.status_code == 200
    assert css.headers["Content-Type"].startswith("text/css")
    assert client.get("/static/login.js").status_code == 200
    assert client.get("/static/fonts/manrope-latin.woff2").status_code == 200


def test_health_probe_is_public(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.get_json()["status"] == "ok"
