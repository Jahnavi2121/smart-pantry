import json
from typing import Optional
from urllib import error as urllib_error
from urllib import parse, request

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from src.api.auth import get_current_user
from src.db.db import get_connection


router = APIRouter(
    prefix="/products",
    tags=["Products"]
)


class ProductCreate(BaseModel):
    name: str
    brand: Optional[str] = None
    barcode: Optional[str] = None


@router.post("", status_code=status.HTTP_201_CREATED)
def create_product(product: ProductCreate):
    connection = get_connection()

    try:
        with connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO products (
                        name,
                        brand,
                        barcode
                    )
                    VALUES (%s, %s, %s)
                    RETURNING
                        id,
                        name,
                        brand,
                        barcode,
                        created_at;
                    """,
                    (
                        product.name,
                        product.brand,
                        product.barcode,
                    ),
                )

                row = cursor.fetchone()

        return {
            "id": row[0],
            "name": row[1],
            "brand": row[2],
            "barcode": row[3],
            "created_at": row[4],
        }

    except Exception as error:
        raise HTTPException(
            status_code=500,
            detail="Unable to create product."
        ) from error

    finally:
        connection.close()


@router.post("/barcode/{barcode}/import")
def import_product_by_barcode(
    barcode: str,
    current_user: dict = Depends(get_current_user)
):
    barcode = barcode.strip()

    if not barcode.isdigit():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Barcode must contain only numbers."
        )

    # First check whether this product is already
    # stored in the Smart Pantry database.
    connection = get_connection()

    try:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT
                    id,
                    name,
                    brand,
                    barcode,
                    created_at
                FROM products
                WHERE barcode = %s;
                """,
                (barcode,),
            )

            existing_product = cursor.fetchone()

        if existing_product is not None:
            return {
                "id": existing_product[0],
                "name": existing_product[1],
                "brand": existing_product[2],
                "barcode": existing_product[3],
                "created_at": existing_product[4],
                "source": "local",
            }

    finally:
        connection.close()

    # Product is not local, so look it up
    # using Open Food Facts.
    encoded_barcode = parse.quote(barcode)

    url = (
        "https://world.openfoodfacts.org"
        f"/api/v3/product/{encoded_barcode}"
        "?fields=code,product_name,brands"
    )

    open_food_facts_request = request.Request(
        url,
        headers={
            "User-Agent": (
                "SmartPantry/0.1 "
                "(RIT Software Engineering Capstone)"
            )
        },
    )

    try:
        with request.urlopen(
            open_food_facts_request,
            timeout=10
        ) as response:
            data = json.loads(
                response.read().decode("utf-8")
            )

    except urllib_error.HTTPError as error:
        if error.code == 404:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Product was not found for this barcode."
            ) from error

        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Open Food Facts returned an error."
        ) from error

    except urllib_error.URLError as error:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Could not connect to Open Food Facts."
        ) from error

    product_data = data.get("product")

    if not product_data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Product was not found for this barcode."
        )

    product_name = (
        product_data.get("product_name") or ""
    ).strip()

    brand = (
        product_data.get("brands") or ""
    ).strip()

    if not product_name:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=(
                "The barcode was found, but the product "
                "does not have a product name."
            )
        )

    if not brand:
        brand = None

    # Store the Open Food Facts product locally.
    connection = get_connection()

    try:
        with connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO products (
                        name,
                        brand,
                        barcode
                    )
                    VALUES (%s, %s, %s)
                    ON CONFLICT (barcode)
                    DO NOTHING
                    RETURNING
                        id,
                        name,
                        brand,
                        barcode,
                        created_at;
                    """,
                    (
                        product_name,
                        brand,
                        barcode,
                    ),
                )

                row = cursor.fetchone()

                # Handles the unlikely case where another
                # request inserted the same barcode first.
                if row is None:
                    cursor.execute(
                        """
                        SELECT
                            id,
                            name,
                            brand,
                            barcode,
                            created_at
                        FROM products
                        WHERE barcode = %s;
                        """,
                        (barcode,),
                    )

                    row = cursor.fetchone()

        return {
            "id": row[0],
            "name": row[1],
            "brand": row[2],
            "barcode": row[3],
            "created_at": row[4],
            "source": "open_food_facts",
        }

    finally:
        connection.close()


@router.get("")
def get_products():
    connection = get_connection()

    try:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT
                    id,
                    name,
                    brand,
                    barcode,
                    created_at
                FROM products
                ORDER BY id;
                """
            )

            rows = cursor.fetchall()

        return [
            {
                "id": row[0],
                "name": row[1],
                "brand": row[2],
                "barcode": row[3],
                "created_at": row[4],
            }
            for row in rows
        ]

    finally:
        connection.close()