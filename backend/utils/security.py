import os

from dotenv import load_dotenv
from passlib.context import CryptContext
from jose import jwt


load_dotenv()


pwd_context = CryptContext(
    schemes=["bcrypt"],
    deprecated="auto"
)


JWT_SECRET = os.getenv(
    "JWT_SECRET",
    "development-secret"
)

JWT_ALGORITHM = os.getenv(
    "JWT_ALGORITHM",
    "HS256"
)


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(
    plain_password: str,
    hashed_password: str
) -> bool:
    return pwd_context.verify(
        plain_password,
        hashed_password
    )


def create_access_token(data: dict) -> str:
    return jwt.encode(
        data,
        JWT_SECRET,
        algorithm=JWT_ALGORITHM
    )