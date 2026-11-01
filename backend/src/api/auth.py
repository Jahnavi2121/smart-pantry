import os
from datetime import datetime, timedelta, timezone

import bcrypt
import jwt

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, EmailStr

from src.db.db import get_connection


router = APIRouter(
    prefix="/auth",
    tags=["Authentication"]
)

security = HTTPBearer()

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


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    token = credentials.credentials

    try:
        payload = jwt.decode(
            token,
            JWT_SECRET,
            algorithms=[JWT_ALGORITHM]
        )

        user_id = int(payload["sub"])

    except jwt.ExpiredSignatureError as error:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Access token has expired."
        ) from error

    except (jwt.InvalidTokenError, KeyError, ValueError) as error:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid access token."
        ) from error

    connection = get_connection()

    try:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT id, name, email
                FROM users
                WHERE id = %s;
                """,
                (user_id,),
            )

            user = cursor.fetchone()

        if user is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User not found."
            )

        return {
            "id": user[0],
            "name": user[1],
            "email": user[2],
        }

    finally:
        connection.close()


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

        password_matches = bcrypt.checkpw(
            login_request.password.encode("utf-8"),
            user[3].encode("utf-8")
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


@router.get("/me")
def get_logged_in_user(
    current_user: dict = Depends(get_current_user)
):
    return current_user