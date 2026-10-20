from datetime import date
from typing import Optional

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from src.db.db import get_connection


router = APIRouter(
    prefix="/inventory",
    tags=["Inventory"]
)


class InventoryCreate(BaseModel):
    household_id: int
    product_id: int
    user_id: int
    quantity: int = Field(default=1, ge=0)
    expiration_date: Optional[date] = None
    low_stock_threshold: int = Field(default=1, ge=0)


class InventoryQuantityChange(BaseModel):
    user_id: int
    change: int


@router.post("", status_code=status.HTTP_201_CREATED)
def create_inventory_item(item: InventoryCreate):
    connection = get_connection()

    try:
        with connection:
            with connection.cursor() as cursor:

                # Verify that the user belongs to the household
                cursor.execute(
                    """
                    SELECT 1
                    FROM household_members
                    WHERE household_id = %s
                      AND user_id = %s;
                    """,
                    (
                        item.household_id,
                        item.user_id,
                    ),
                )

                if cursor.fetchone() is None:
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail="User is not a member of this household."
                    )

                # Verify that the product exists
                cursor.execute(
                    """
                    SELECT id
                    FROM products
                    WHERE id = %s;
                    """,
                    (item.product_id,),
                )

                if cursor.fetchone() is None:
                    raise HTTPException(
                        status_code=status.HTTP_404_NOT_FOUND,
                        detail="Product not found."
                    )

                # Add item to inventory
                cursor.execute(
                    """
                    INSERT INTO inventory_items (
                        household_id,
                        product_id,
                        quantity,
                        expiration_date,
                        low_stock_threshold
                    )
                    VALUES (%s, %s, %s, %s, %s)
                    RETURNING
                        id,
                        household_id,
                        product_id,
                        quantity,
                        expiration_date,
                        low_stock_threshold,
                        is_active,
                        created_at,
                        updated_at;
                    """,
                    (
                        item.household_id,
                        item.product_id,
                        item.quantity,
                        item.expiration_date,
                        item.low_stock_threshold,
                    ),
                )

                row = cursor.fetchone()

                # Record creation in inventory history
                cursor.execute(
                    """
                    INSERT INTO inventory_history (
                        inventory_item_id,
                        user_id,
                        action,
                        old_quantity,
                        new_quantity
                    )
                    VALUES (%s, %s, %s, %s, %s);
                    """,
                    (
                        row[0],
                        item.user_id,
                        "ADD",
                        0,
                        item.quantity,
                    ),
                )

        return {
            "id": row[0],
            "household_id": row[1],
            "product_id": row[2],
            "quantity": row[3],
            "expiration_date": row[4],
            "low_stock_threshold": row[5],
            "is_active": row[6],
            "created_at": row[7],
            "updated_at": row[8],
        }

    finally:
        connection.close()


@router.patch("/{inventory_item_id}/quantity")
def update_inventory_quantity(
    inventory_item_id: int,
    update: InventoryQuantityChange
):
    connection = get_connection()

    try:
        with connection:
            with connection.cursor() as cursor:

                # Lock the row while the quantity is being updated
                cursor.execute(
                    """
                    SELECT household_id, quantity
                    FROM inventory_items
                    WHERE id = %s
                      AND is_active = TRUE
                    FOR UPDATE;
                    """,
                    (inventory_item_id,),
                )

                row = cursor.fetchone()

                if row is None:
                    raise HTTPException(
                        status_code=status.HTTP_404_NOT_FOUND,
                        detail="Inventory item not found."
                    )

                household_id = row[0]
                old_quantity = row[1]

                # Verify that the user belongs to the household
                cursor.execute(
                    """
                    SELECT 1
                    FROM household_members
                    WHERE household_id = %s
                      AND user_id = %s;
                    """,
                    (
                        household_id,
                        update.user_id,
                    ),
                )

                if cursor.fetchone() is None:
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail="User is not a member of this household."
                    )

                if update.change == 0:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="Quantity change cannot be zero."
                    )

                new_quantity = old_quantity + update.change

                if new_quantity < 0:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="Quantity cannot be less than zero."
                    )

                # Update the inventory quantity
                cursor.execute(
                    """
                    UPDATE inventory_items
                    SET quantity = %s,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE id = %s
                    RETURNING quantity, updated_at;
                    """,
                    (
                        new_quantity,
                        inventory_item_id,
                    ),
                )

                updated_row = cursor.fetchone()

                action = "CONSUME" if update.change < 0 else "RESTOCK"

                # Record the quantity change
                cursor.execute(
                    """
                    INSERT INTO inventory_history (
                        inventory_item_id,
                        user_id,
                        action,
                        old_quantity,
                        new_quantity
                    )
                    VALUES (%s, %s, %s, %s, %s);
                    """,
                    (
                        inventory_item_id,
                        update.user_id,
                        action,
                        old_quantity,
                        new_quantity,
                    ),
                )

        return {
            "inventory_item_id": inventory_item_id,
            "old_quantity": old_quantity,
            "change": update.change,
            "new_quantity": updated_row[0],
            "updated_at": updated_row[1],
        }

    finally:
        connection.close()

@router.get("/{inventory_item_id}/history")
def get_inventory_history(inventory_item_id: int):
    connection = get_connection()

    try:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT
                    h.id,
                    h.inventory_item_id,
                    h.user_id,
                    u.name,
                    h.action,
                    h.old_quantity,
                    h.new_quantity,
                    h.created_at
                FROM inventory_history h
                JOIN users u
                    ON h.user_id = u.id
                WHERE h.inventory_item_id = %s
                ORDER BY h.created_at DESC, h.id DESC;
                """,
                (inventory_item_id,),
            )

            rows = cursor.fetchall()

        return [
            {
                "id": row[0],
                "inventory_item_id": row[1],
                "user_id": row[2],
                "user_name": row[3],
                "action": row[4],
                "old_quantity": row[5],
                "new_quantity": row[6],
                "created_at": row[7],
            }
            for row in rows
        ]

    finally:
        connection.close()

@router.get("/{household_id}/low-stock")
def get_low_stock_items(household_id: int):
    connection = get_connection()

    try:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT
                    i.id,
                    i.household_id,
                    i.product_id,
                    p.name,
                    p.brand,
                    i.quantity,
                    i.low_stock_threshold,
                    i.expiration_date
                FROM inventory_items i
                JOIN products p
                    ON i.product_id = p.id
                WHERE i.household_id = %s
                  AND i.is_active = TRUE
                  AND i.quantity <= i.low_stock_threshold
                ORDER BY i.quantity ASC, i.id ASC;
                """,
                (household_id,),
            )

            rows = cursor.fetchall()

        return [
            {
                "id": row[0],
                "household_id": row[1],
                "product_id": row[2],
                "product_name": row[3],
                "brand": row[4],
                "quantity": row[5],
                "low_stock_threshold": row[6],
                "expiration_date": row[7],
            }
            for row in rows
        ]

    finally:
        connection.close()

@router.get("/{household_id}/expiring-soon")
def get_expiring_soon_items(household_id: int, days: int = 7):
    if days < 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Days cannot be negative."
        )

    connection = get_connection()

    try:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT
                    i.id,
                    i.household_id,
                    i.product_id,
                    p.name,
                    p.brand,
                    i.quantity,
                    i.expiration_date
                FROM inventory_items i
                JOIN products p
                    ON i.product_id = p.id
                WHERE i.household_id = %s
                  AND i.is_active = TRUE
                  AND i.expiration_date IS NOT NULL
                  AND i.expiration_date >= CURRENT_DATE
                  AND i.expiration_date <= CURRENT_DATE + %s
                ORDER BY i.expiration_date ASC, i.id ASC;
                """,
                (
                    household_id,
                    days,
                ),
            )

            rows = cursor.fetchall()

        return [
            {
                "id": row[0],
                "household_id": row[1],
                "product_id": row[2],
                "product_name": row[3],
                "brand": row[4],
                "quantity": row[5],
                "expiration_date": row[6],
            }
            for row in rows
        ]

    finally:
        connection.close()
@router.delete("/{inventory_item_id}")
def remove_inventory_item(
    inventory_item_id: int,
    user_id: int
):
    connection = get_connection()

    try:
        with connection:
            with connection.cursor() as cursor:

                cursor.execute(
                    """
                    SELECT household_id, quantity
                    FROM inventory_items
                    WHERE id = %s
                      AND is_active = TRUE
                    FOR UPDATE;
                    """,
                    (inventory_item_id,),
                )

                item = cursor.fetchone()

                if item is None:
                    raise HTTPException(
                        status_code=status.HTTP_404_NOT_FOUND,
                        detail="Inventory item not found."
                    )

                household_id = item[0]
                old_quantity = item[1]

                # Verify user belongs to household
                cursor.execute(
                    """
                    SELECT 1
                    FROM household_members
                    WHERE household_id = %s
                      AND user_id = %s;
                    """,
                    (
                        household_id,
                        user_id,
                    ),
                )

                if cursor.fetchone() is None:
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail="User is not a member of this household."
                    )

                # Soft-delete the inventory item
                cursor.execute(
                    """
                    UPDATE inventory_items
                    SET quantity = 0,
                        is_active = FALSE,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE id = %s;
                    """,
                    (inventory_item_id,),
                )

                # Record removal in history
                cursor.execute(
                    """
                    INSERT INTO inventory_history (
                        inventory_item_id,
                        user_id,
                        action,
                        old_quantity,
                        new_quantity
                    )
                    VALUES (%s, %s, %s, %s, %s);
                    """,
                    (
                        inventory_item_id,
                        user_id,
                        "REMOVE",
                        old_quantity,
                        0,
                    ),
                )

        return {
            "message": "Inventory item removed successfully.",
            "inventory_item_id": inventory_item_id
        }

    finally:
        connection.close()

@router.get("/{household_id}")
def get_inventory(household_id: int):
    connection = get_connection()

    try:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT
                    i.id,
                    i.household_id,
                    i.product_id,
                    p.name,
                    p.brand,
                    p.barcode,
                    i.quantity,
                    i.expiration_date,
                    i.low_stock_threshold,
                    i.is_active,
                    i.created_at,
                    i.updated_at
                FROM inventory_items i
                JOIN products p
                    ON i.product_id = p.id
                WHERE i.household_id = %s
                  AND i.is_active = TRUE
                ORDER BY i.id;
                """,
                (household_id,),
            )

            rows = cursor.fetchall()

        return [
            {
                "id": row[0],
                "household_id": row[1],
                "product_id": row[2],
                "product_name": row[3],
                "brand": row[4],
                "barcode": row[5],
                "quantity": row[6],
                "expiration_date": row[7],
                "low_stock_threshold": row[8],
                "is_active": row[9],
                "created_at": row[10],
                "updated_at": row[11],
            }
            for row in rows
        ]

    finally:
        connection.close()
