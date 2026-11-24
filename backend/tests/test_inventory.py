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


def test_inventory_requires_authentication():
    response = client.get(
        f"/inventory/{HOUSEHOLD_ID}"
    )

    assert response.status_code == 401


def test_get_household_inventory():
    headers = get_auth_headers()

    response = client.get(
        f"/inventory/{HOUSEHOLD_ID}",
        headers=headers,
    )

    assert response.status_code == 200

    data = response.json()

    assert isinstance(data, list)

    if len(data) > 0:
        item = data[0]

        assert "id" in item
        assert "product_name" in item
        assert "quantity" in item
        assert "low_stock_threshold" in item


def test_nonexistent_inventory_item_returns_404():
    headers = get_auth_headers()

    response = client.patch(
        "/inventory/999999/quantity",
        headers=headers,
        json={
            "change": 1
        },
    )

    assert response.status_code == 404
    assert response.json() == {
        "detail": "Inventory item not found."
    }


def test_zero_quantity_change_is_rejected():
    headers = get_auth_headers()

    inventory_response = client.get(
        f"/inventory/{HOUSEHOLD_ID}",
        headers=headers,
    )

    assert inventory_response.status_code == 200

    inventory = inventory_response.json()

    assert len(inventory) > 0

    inventory_item_id = inventory[0]["id"]

    response = client.patch(
        f"/inventory/{inventory_item_id}/quantity",
        headers=headers,
        json={
            "change": 0
        },
    )

    assert response.status_code == 400
    assert response.json() == {
        "detail": "Quantity change cannot be zero."
    }


def test_quantity_cannot_go_below_zero():
    headers = get_auth_headers()

    inventory_response = client.get(
        f"/inventory/{HOUSEHOLD_ID}",
        headers=headers,
    )

    assert inventory_response.status_code == 200

    inventory = inventory_response.json()

    assert len(inventory) > 0

    item = inventory[0]

    inventory_item_id = item["id"]
    current_quantity = item["quantity"]

    response = client.patch(
        f"/inventory/{inventory_item_id}/quantity",
        headers=headers,
        json={
            "change": -(current_quantity + 1)
        },
    )

    assert response.status_code == 400
    assert response.json() == {
        "detail": "Quantity cannot be less than zero."
    }


def test_low_stock_endpoint():
    headers = get_auth_headers()

    response = client.get(
        f"/inventory/{HOUSEHOLD_ID}/low-stock",
        headers=headers,
    )

    assert response.status_code == 200
    assert isinstance(response.json(), list)


def test_expiring_soon_endpoint():
    headers = get_auth_headers()

    response = client.get(
        f"/inventory/{HOUSEHOLD_ID}/expiring-soon?days=14",
        headers=headers,
    )

    assert response.status_code == 200
    assert isinstance(response.json(), list)