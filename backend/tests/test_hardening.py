"""Sprint 6 hardening: login throttling, password change and token revocation,
security headers, production configuration and serving the built frontend."""

import time

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.core.config import Settings
from app.main import mount_frontend
from tests.conftest import PASSWORD, login

S1 = "s1"


def try_login(client, username, password):
    return client.post("/api/auth/login", data={"username": username, "password": password})


def test_login_is_throttled_after_repeated_failures(client, world):
    for _ in range(5):
        assert try_login(client, S1, "wrong-password").status_code == 401
    blocked = try_login(client, S1, PASSWORD)  # even the right password waits
    assert blocked.status_code == 429
    assert int(blocked.headers["Retry-After"]) > 0
    # Other accounts are not affected.
    assert try_login(client, "s2", PASSWORD).status_code == 200


def test_success_resets_the_failure_counter(client, world):
    for _ in range(4):
        try_login(client, S1, "wrong-password")
    assert try_login(client, S1, PASSWORD).status_code == 200
    for _ in range(4):
        assert try_login(client, S1, "wrong-password").status_code == 401


def test_password_change_revokes_old_tokens(client, world):
    old = login(client, S1)
    url = "/api/auth/password"
    wrong = {"current_password": "nope", "new_password": "a-brand-new-password"}
    assert client.put(url, headers=old, json=wrong).status_code == 400
    same = {"current_password": PASSWORD, "new_password": PASSWORD}
    assert client.put(url, headers=old, json=same).status_code == 422

    time.sleep(1.1)  # tokens carry whole seconds: make the old one strictly older
    r = client.put(
        url,
        headers=old,
        json={"current_password": PASSWORD, "new_password": "a-brand-new-password"},
    )
    assert r.status_code == 200
    fresh = {"Authorization": f"Bearer {r.json()['access_token']}"}

    assert client.get("/api/auth/me", headers=old).status_code == 401
    assert client.get("/api/auth/me", headers=fresh).status_code == 200
    login(client, S1, "a-brand-new-password")


def test_admin_reset_closes_user_sessions(client, world):
    student = login(client, S1)
    admin = login(client, "admin")
    time.sleep(1.1)
    s1_id = world["users"]["s1"].user_id
    r = client.patch(f"/api/users/{s1_id}", headers=admin, json={"password": "reset-by-admin-123"})
    assert r.status_code == 200
    assert client.get("/api/auth/me", headers=student).status_code == 401


def test_security_headers(client, world):
    r = client.get("/api/auth/me", headers=login(client, S1))
    assert r.headers["X-Content-Type-Options"] == "nosniff"
    assert r.headers["X-Frame-Options"] == "DENY"
    assert r.headers["Cache-Control"] == "no-store"
    assert "default-src 'self'" in r.headers["Content-Security-Policy"]
    # Swagger UI needs its CDN scripts, so the docs are excluded from the CSP.
    assert "Content-Security-Policy" not in client.get("/docs").headers


def test_production_requires_a_real_jwt_secret():
    with pytest.raises(ValidationError):
        Settings(environment="production", _env_file=None)
    with pytest.raises(ValidationError):
        Settings(environment="production", jwt_secret="short", _env_file=None)
    ok = Settings(environment="production", jwt_secret="x" * 40, _env_file=None)
    assert ok.is_production


def test_built_frontend_is_served_with_spa_fallback(tmp_path):
    (tmp_path / "assets").mkdir()
    (tmp_path / "index.html").write_text("<html>app</html>")
    (tmp_path / "assets" / "app.js").write_text("console.log(1)")
    (tmp_path / "favicon.svg").write_text("<svg/>")
    spa = FastAPI()
    mount_frontend(spa, tmp_path)
    client = TestClient(spa)

    assert client.get("/assets/app.js").text == "console.log(1)"
    assert client.get("/favicon.svg").text == "<svg/>"
    # Client-side routes return the app shell.
    assert client.get("/theses/5").text == "<html>app</html>"
    # Unknown API paths stay 404, and files outside the folder are never served.
    assert client.get("/api/unknown").status_code == 404
    assert client.get("/..%2F..%2Fetc%2Fpasswd").text == "<html>app</html>"
