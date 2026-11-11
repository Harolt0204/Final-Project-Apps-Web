from tests.conftest import PASSWORD, login


def test_health(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "database": "ok"}


def test_login_returns_token_and_user(client, world):
    response = client.post(
        "/api/auth/login", data={"username": "PA@yachaytech.edu.ec", "password": PASSWORD}
    )
    assert response.status_code == 200
    body = response.json()
    assert body["token_type"] == "bearer"
    assert body["user"]["role"] == "professor"
    assert "password_hash" not in body["user"]


def test_login_rejects_wrong_password_and_unknown_email_alike(client, world):
    wrong = client.post(
        "/api/auth/login", data={"username": "pA@yachaytech.edu.ec", "password": "nope"}
    )
    unknown = client.post(
        "/api/auth/login", data={"username": "ghost@yachaytech.edu.ec", "password": PASSWORD}
    )
    assert wrong.status_code == unknown.status_code == 401
    assert wrong.json() == unknown.json()


def test_me_requires_a_valid_token(client, world):
    assert client.get("/api/auth/me").status_code == 401
    bad = {"Authorization": "Bearer not-a-jwt"}
    assert client.get("/api/auth/me", headers=bad).status_code == 401

    headers = login(client, "s1@yachaytech.edu.ec")
    me = client.get("/api/auth/me", headers=headers).json()
    assert me["role"] == "student"
    assert me["display_name"] == "s1 Student"


def test_deactivated_user_loses_access_immediately(client, world):
    student_headers = login(client, "s1@yachaytech.edu.ec")
    admin_headers = login(client, "admin@yachaytech.edu.ec")
    s1_id = world["users"]["s1"].user_id

    r = client.patch(f"/api/users/{s1_id}", json={"is_active": False}, headers=admin_headers)
    assert r.status_code == 200
    assert client.get("/api/auth/me", headers=student_headers).status_code == 401
    r = client.post(
        "/api/auth/login", data={"username": "s1@yachaytech.edu.ec", "password": PASSWORD}
    )
    assert r.status_code == 401


def test_only_admins_manage_users(client, world):
    prof_headers = login(client, "pA@yachaytech.edu.ec")
    assert client.get("/api/users", headers=prof_headers).status_code == 403

    admin_headers = login(client, "admin@yachaytech.edu.ec")
    users = client.get("/api/users", headers=admin_headers).json()
    assert len(users) == 7


def test_create_user_validates_role_link_and_duplicates(client, world):
    headers = login(client, "admin@yachaytech.edu.ec")
    # A student account must be linked to a student, not to a professor.
    r = client.post(
        "/api/users",
        headers=headers,
        json={
            "email": "new@yachaytech.edu.ec",
            "password": "long-enough-pass",
            "role": "student",
            "professor_id": world["profs"]["pC"].professor_id,
        },
    )
    assert r.status_code == 422

    r = client.post(
        "/api/users",
        headers=headers,
        json={
            "email": "new.admin@yachaytech.edu.ec",
            "password": "short",
            "role": "admin",
        },
    )
    assert r.status_code == 422

    payload = {
        "email": "new.admin@yachaytech.edu.ec",
        "password": "long-enough-pass",
        "role": "admin",
    }
    assert client.post("/api/users", headers=headers, json=payload).status_code == 201
    assert client.post("/api/users", headers=headers, json=payload).status_code == 409


def test_admin_cannot_deactivate_self(client, world):
    headers = login(client, "admin@yachaytech.edu.ec")
    admin_id = world["users"]["admin"].user_id
    r = client.patch(f"/api/users/{admin_id}", json={"is_active": False}, headers=headers)
    assert r.status_code == 409
