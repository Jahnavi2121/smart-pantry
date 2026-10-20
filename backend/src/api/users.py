import bcrypt
import psycopg2

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, EmailStr

from src.db.db import get_connection


router = APIRouter(
    prefix="/users",
    tags=["Users"]
)


class UserCreate(BaseModel):
    name: str
    email: EmailStr
    password: str


@router.post("", status_code=status.HTTP_201_CREATED)
def create_user(user: UserCreate):
    password_hash = bcrypt.hashpw(
        user.password.encode("utf-8"),
        bcrypt.gensalt()
    ).decode("utf-8")

    connection = get_connection()

    try:
        with connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO users (name, email, password_hash)
                    VALUES (%s, %s, %s)
                    RETURNING id, name, email, created_at;
                    """,
                    (
                        user.name,
                        user.email,
                        password_hash,
                    ),
                )

                row = cursor.fetchone()

        return {
            "id": row[0],
            "name": row[1],
            "email": row[2],
            "created_at": row[3],
        }

    except psycopg2.errors.UniqueViolation as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A user with this email already exists."
        ) from error

    finally:
        connection.close()


@router.get("")
def get_users():
    connection = get_connection()

    try:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT id, name, email, created_at
                FROM users
                ORDER BY id;
                """
            )

            rows = cursor.fetchall()

        return [
            {
                "id": row[0],
                "name": row[1],
                "email": row[2],
                "created_at": row[3],
            }
            for row in rows
        ]

    finally:
        connection.close()