"""
Tests for Health, Registration, Login, and Current User endpoints.
"""
def test_health_check(client):
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert "app" in data


def test_user_registration_and_login(client):
    # 1. Register new user
    user_payload = {
        "name": "Arjun Sharma",
        "email": "arjun@test.com",
        "password": "securepassword123",
        "organization": "Test Corp",
        "industry": "Manufacturing",
        "role": "Quality Manager",
    }
    res = client.post("/api/auth/register", json=user_payload)
    assert res.status_code == 201
    data = res.json()
    assert "access_token" in data
    assert data["user"]["email"] == "arjun@test.com"
    assert "password" not in data["user"]
    assert "password_hash" not in data["user"]

    token = data["access_token"]

    # 2. Duplicate registration should fail (409 Conflict)
    dup_res = client.post("/api/auth/register", json=user_payload)
    assert dup_res.status_code == 409

    # 3. Login with correct credentials
    login_res = client.post("/api/auth/login", json={
        "email": "arjun@test.com",
        "password": "securepassword123",
    })
    assert login_res.status_code == 200
    login_data = login_res.json()
    assert "access_token" in login_data

    # 4. Login with incorrect password should fail (401)
    wrong_login = client.post("/api/auth/login", json={
        "email": "arjun@test.com",
        "password": "wrongpassword",
    })
    assert wrong_login.status_code == 401

    # 5. Access /api/auth/me with Bearer token
    headers = {"Authorization": f"Bearer {token}"}
    me_res = client.get("/api/auth/me", headers=headers)
    assert me_res.status_code == 200
    assert me_res.json()["email"] == "arjun@test.com"

    # 6. Access /api/auth/me without token should fail (401/403)
    unauth_res = client.get("/api/auth/me")
    assert unauth_res.status_code in (401, 403)
