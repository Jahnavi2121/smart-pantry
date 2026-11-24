from fastapi.testclient import TestClient

from src.server import app


client = TestClient(app)


def test_auth_me_requires_token():
    response = client.get("/auth/me")

    assert response.status_code == 401
    assert response.json() == {
        "detail": "Not authenticated"
    }


def test_auth_me_rejects_invalid_token():
    response = client.get(
        "/auth/me",
        headers={
            "Authorization": "Bearer invalid-token"
        },
    )

    assert response.status_code == 401
    assert response.json() == {
        "detail": "Invalid access token."
    }


def test_login_success():
    response = client.post(
        "/auth/login",
        json={
            "email": "jahnavi@example.com",
            "password": "TestPassword123",
        },
    )

    assert response.status_code == 200

    data = response.json()

    assert "access_token" in data
    assert data["token_type"] == "bearer"
    assert data["user"]["email"] == "jahnavi@example.com"
    assert data["user"]["name"] == "Jahnavi Kaja"


def test_auth_me_with_valid_token():
    login_response = client.post(
        "/auth/login",
        json={
            "email": "jahnavi@example.com",
            "password": "TestPassword123",
        },
    )

    assert login_response.status_code == 200

    token = login_response.json()["access_token"]

    response = client.get(
        "/auth/me",
        headers={
            "Authorization": f"Bearer {token}"
        },
    )

    assert response.status_code == 200

    data = response.json()

    assert data["email"] == "jahnavi@example.com"
    assert data["name"] == "Jahnavi Kaja"