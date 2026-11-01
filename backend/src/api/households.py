import psycopg2

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from src.api.auth import get_current_user
from src.db.db import get_connection


router = APIRouter(
    prefix="/households",
    tags=["Households"]
)


class HouseholdCreate(BaseModel):
    name: str


class HouseholdMemberAdd(BaseModel):
    user_id: int


@router.post("", status_code=status.HTTP_201_CREATED)
def create_household(
    household: HouseholdCreate,
    current_user: dict = Depends(get_current_user)
):
    connection = get_connection()

    try:
        with connection:
            with connection.cursor() as cursor:

                cursor.execute(
                    """
                    INSERT INTO households (
                        name,
                        created_by
                    )
                    VALUES (%s, %s)
                    RETURNING id, name, created_by, created_at;
                    """,
                    (
                        household.name,
                        current_user["id"],
                    ),
                )

                row = cursor.fetchone()

                cursor.execute(
                    """
                    INSERT INTO household_members (
                        household_id,
                        user_id,
                        role
                    )
                    VALUES (%s, %s, %s);
                    """,
                    (
                        row[0],
                        current_user["id"],
                        "owner",
                    ),
                )

        return {
            "id": row[0],
            "name": row[1],
            "created_by": row[2],
            "created_at": row[3],
        }

    finally:
        connection.close()


@router.get("")
def get_households(
    current_user: dict = Depends(get_current_user)
):
    connection = get_connection()

    try:
        with connection.cursor() as cursor:

            cursor.execute(
                """
                SELECT
                    h.id,
                    h.name,
                    h.created_by,
                    h.created_at,
                    hm.role
                FROM households h
                JOIN household_members hm
                    ON h.id = hm.household_id
                WHERE hm.user_id = %s
                ORDER BY h.id;
                """,
                (current_user["id"],),
            )

            rows = cursor.fetchall()

        return [
            {
                "id": row[0],
                "name": row[1],
                "created_by": row[2],
                "created_at": row[3],
                "role": row[4],
            }
            for row in rows
        ]

    finally:
        connection.close()


@router.post("/{household_id}/members")
def add_household_member(
    household_id: int,
    member: HouseholdMemberAdd,
    current_user: dict = Depends(get_current_user)
):
    connection = get_connection()

    try:
        with connection:
            with connection.cursor() as cursor:

                # Current user must be the household owner
                cursor.execute(
                    """
                    SELECT 1
                    FROM household_members
                    WHERE household_id = %s
                      AND user_id = %s
                      AND role = 'owner';
                    """,
                    (
                        household_id,
                        current_user["id"],
                    ),
                )

                if cursor.fetchone() is None:
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail="Only the household owner can add members."
                    )

                # Make sure the new user exists
                cursor.execute(
                    """
                    SELECT id
                    FROM users
                    WHERE id = %s;
                    """,
                    (member.user_id,),
                )

                if cursor.fetchone() is None:
                    raise HTTPException(
                        status_code=status.HTTP_404_NOT_FOUND,
                        detail="User not found."
                    )

                try:
                    cursor.execute(
                        """
                        INSERT INTO household_members (
                            household_id,
                            user_id,
                            role
                        )
                        VALUES (%s, %s, %s);
                        """,
                        (
                            household_id,
                            member.user_id,
                            "member",
                        ),
                    )

                except psycopg2.errors.UniqueViolation as error:
                    raise HTTPException(
                        status_code=status.HTTP_409_CONFLICT,
                        detail="User is already a member of this household."
                    ) from error

        return {
            "message": "Household member added successfully.",
            "household_id": household_id,
            "user_id": member.user_id,
            "role": "member",
        }

    finally:
        connection.close()


@router.get("/{household_id}/members")
def get_household_members(
    household_id: int,
    current_user: dict = Depends(get_current_user)
):
    connection = get_connection()

    try:
        with connection.cursor() as cursor:

            # User requesting the list must belong to the household
            cursor.execute(
                """
                SELECT 1
                FROM household_members
                WHERE household_id = %s
                  AND user_id = %s;
                """,
                (
                    household_id,
                    current_user["id"],
                ),
            )

            if cursor.fetchone() is None:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="You are not a member of this household."
                )

            cursor.execute(
                """
                SELECT
                    u.id,
                    u.name,
                    u.email,
                    hm.role,
                    hm.joined_at
                FROM household_members hm
                JOIN users u
                    ON hm.user_id = u.id
                WHERE hm.household_id = %s
                ORDER BY hm.joined_at, u.id;
                """,
                (household_id,),
            )

            rows = cursor.fetchall()

        return [
            {
                "id": row[0],
                "name": row[1],
                "email": row[2],
                "role": row[3],
                "joined_at": row[4],
            }
            for row in rows
        ]

    finally:
        connection.close()