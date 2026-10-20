import os
from datetime import datetime, timedelta, timezone

import bcrypt
import jwt

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, EmailStr

from src.db.db import get_connection


router = APIRouter(
    prefix="/auth",
    tags=["Authentication"]
)


JWT_SECRET = os.getenv(
    "SMART_PANTRY_JWT_SECRET",
    "smart-pantry-development-secret"
)

JWT_ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


def create_access_token(user_id: int, email: str):
    expiration = datetime.now(timezone.utc) + timedelta(
        minutes=ACCESS_TOKEN_EXPIRE_MINUTES
    )

    payload = {
        "sub": str(user_id),
        "email": email,
        "exp": expiration,
    }

    return jwt.encode(
        payload,
        JWT_SECRET,
        algorithm=JWT_ALGORITHM
    )


@router.post("/login")
def login(login_request: LoginRequest):
    connection = get_connection()

    try:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT id, name, email, password_hash
                FROM users
                WHERE email = %s;
                """,
                (login_request.email,),
            )

            user = cursor.fetchone()

        if user is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid email or password."
            )

        stored_password_hash = user[3].encode("utf-8")

        password_matches = bcrypt.checkpw(
            login_request.password.encode("utf-8"),
            stored_password_hash
        )

        if not password_matches:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid email or password."
            )

        access_token = create_access_token(
            user_id=user[0],
            email=user[2]
        )

        return {
            "access_token": access_token,
            "token_type": "bearer",
            "user": {
                "id": user[0],
                "name": user[1],
                "email": user[2],
            }
        }

    finally:
        connection.close()