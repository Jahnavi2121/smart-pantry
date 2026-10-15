from typing import Optional

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel

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
                    INSERT INTO products (name, brand, barcode)
                    VALUES (%s, %s, %s)
                    RETURNING id, name, brand, barcode, created_at;
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


@router.get("")
def get_products():
    connection = get_connection()

    try:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT id, name, brand, barcode, created_at
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