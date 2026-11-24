from fastapi.testclient import TestClient

from src.server import app


client = TestClient(app)

TEST_EMAIL = "jahnavi@example.com"
TEST_PASSWORD = "TestPassword123"

NUTELLA_BARCODE = "3017624010701"


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


def test_get_products():
    response = client.get("/products")

    assert response.status_code == 200

    data = response.json()

    assert isinstance(data, list)

    if len(data) > 0:
        product = data[0]

        assert "id" in product
        assert "name" in product
        assert "barcode" in product


def test_barcode_import_requires_authentication():
    response = client.post(
        f"/products/barcode/{NUTELLA_BARCODE}/import"
    )

    assert response.status_code == 401


def test_barcode_must_be_numeric():
    headers = get_auth_headers()

    response = client.post(
        "/products/barcode/not-a-barcode/import",
        headers=headers,
    )

    assert response.status_code == 400
    assert response.json() == {
        "detail": "Barcode must contain only numbers."
    }


def test_existing_barcode_product_can_be_loaded():
    headers = get_auth_headers()

    response = client.post(
        f"/products/barcode/{NUTELLA_BARCODE}/import",
        headers=headers,
    )

    assert response.status_code == 200

    data = response.json()

    assert data["barcode"] == NUTELLA_BARCODE
    assert "id" in data
    assert "name" in data
    assert data["source"] == "local"