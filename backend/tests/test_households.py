from fastapi.testclient import TestClient

from src.server import app


client = TestClient(app)

TEST_EMAIL = "jahnavi@example.com"
TEST_PASSWORD = "TestPassword123"
HOUSEHOLD_ID = 1


def get_auth_headers():
    response = client.post(
        "/auth/login",
        json={
            "email": TEST_EMAIL,
            "password": TEST_PASSWORD,
        },
    )

    assert response.status_code == 200

    token = response.json()["access_token"]

    return {
        "Authorization": f"Bearer {token}"
    }


def test_households_requires_authentication():
    response = client.get("/households")

    assert response.status_code == 401


def test_get_user_households():
    headers = get_auth_headers()

    response = client.get(
        "/households",
        headers=headers,
    )

    assert response.status_code == 200

    data = response.json()

    assert isinstance(data, list)
    assert len(data) > 0

    household = data[0]

    assert "id" in household
    assert "name" in household
    assert "role" in household


def test_get_household_members():
    headers = get_auth_headers()

    response = client.get(
        f"/households/{HOUSEHOLD_ID}/members",
        headers=headers,
    )

    assert response.status_code == 200

    data = response.json()

    assert isinstance(data, list)
    assert len(data) > 0

    member = data[0]

    assert "id" in member
    assert "name" in member
    assert "email" in member
    assert "role" in member


def test_household_owner_is_present():
    headers = get_auth_headers()

    response = client.get(
        f"/households/{HOUSEHOLD_ID}/members",
        headers=headers,
    )

    assert response.status_code == 200

    members = response.json()

    owner_exists = any(
        member["role"] == "owner"
        for member in members
    )

    assert owner_exists