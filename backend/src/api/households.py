from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel

from src.db.db import get_connection


router = APIRouter(
    prefix="/households",
    tags=["Households"]
)


class HouseholdCreate(BaseModel):
    name: str
    created_by: int


class HouseholdMemberAdd(BaseModel):
    owner_user_id: int
    user_id: int


@router.post("", status_code=status.HTTP_201_CREATED)
def create_household(household: HouseholdCreate):
    connection = get_connection()

    try:
        with connection:
            with connection.cursor() as cursor:

                # Verify creator exists
                cursor.execute(
                    """
                    SELECT id
                    FROM users
                    WHERE id = %s;
                    """,
                    (household.created_by,)
                )

                if cursor.fetchone() is None:
                    raise HTTPException(
                        status_code=status.HTTP_404_NOT_FOUND,
                        detail="User not found."
                    )

                # Create household
                cursor.execute(
                    """
                    INSERT INTO households (name, created_by)
                    VALUES (%s, %s)
                    RETURNING id, name, created_by, created_at;
                    """,
                    (
                        household.name,
                        household.created_by
                    ),
                )

                row = cursor.fetchone()
                household_id = row[0]

                # Automatically add creator as owner
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
                        household.created_by,
                        "owner"
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
def get_households():
    connection = get_connection()

    try:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT id, name, created_by, created_at
                FROM households
                ORDER BY id;
                """
            )

            rows = cursor.fetchall()

        return [
            {
                "id": row[0],
                "name": row[1],
                "created_by": row[2],
                "created_at": row[3],
            }
            for row in rows
        ]

    finally:
        connection.close()


@router.post(
    "/{household_id}/members",
    status_code=status.HTTP_201_CREATED
)
def add_household_member(
    household_id: int,
    member: HouseholdMemberAdd
):
    connection = get_connection()

    try:
        with connection:
            with connection.cursor() as cursor:

                # Verify requesting user is the household owner
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
                        member.owner_user_id,
                    ),
                )

                if cursor.fetchone() is None:
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail="Only the household owner can add members."
                    )

                # Verify new user exists
                cursor.execute(
                    """
                    SELECT id, name, email
                    FROM users
                    WHERE id = %s;
                    """,
                    (member.user_id,),
                )

                user = cursor.fetchone()

                if user is None:
                    raise HTTPException(
                        status_code=status.HTTP_404_NOT_FOUND,
                        detail="User not found."
                    )

                # Add member
                cursor.execute(
                    """
                    INSERT INTO household_members (
                        household_id,
                        user_id,
                        role
                    )
                    VALUES (%s, %s, 'member')
                    ON CONFLICT (household_id, user_id)
                    DO NOTHING
                    RETURNING household_id, user_id, role, joined_at;
                    """,
                    (
                        household_id,
                        member.user_id,
                    ),
                )

                membership = cursor.fetchone()

                if membership is None:
                    raise HTTPException(
                        status_code=status.HTTP_409_CONFLICT,
                        detail="User is already a member of this household."
                    )

        return {
            "household_id": membership[0],
            "user_id": membership[1],
            "user_name": user[1],
            "email": user[2],
            "role": membership[2],
            "joined_at": membership[3],
        }

    finally:
        connection.close()


@router.get("/{household_id}/members")
def get_household_members(household_id: int):
    connection = get_connection()

    try:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT
                    hm.user_id,
                    u.name,
                    u.email,
                    hm.role,
                    hm.joined_at
                FROM household_members hm
                JOIN users u
                    ON hm.user_id = u.id
                WHERE hm.household_id = %s
                ORDER BY hm.joined_at;
                """,
                (household_id,),
            )

            rows = cursor.fetchall()

        return [
            {
                "user_id": row[0],
                "name": row[1],
                "email": row[2],
                "role": row[3],
                "joined_at": row[4],
            }
            for row in rows
        ]

    finally:
        connection.close()