"""Login and permission checks: FastAPI dependencies and the /auth/login route."""

from typing import Annotated

import jwt
from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from sqlalchemy import select
from sqlalchemy.orm import Session

from db import get_db
from models import User
from schemas import Token
from security import (
    DUMMY_HASH,
    create_access_token,
    password_hash,
    read_access_token,
)

SessionDep = Annotated[Session, Depends(get_db)]
# auto_error=False: no header -> None instead of an automatic 401; we decide
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/login", auto_error=False)
router = APIRouter(prefix="/auth", tags=["auth"])


def unauthorized(detail: str) -> HTTPException:
    # RFC 9110, §15.5.2: a 401 must carry WWW-Authenticate
    return HTTPException(401, detail, headers={"WWW-Authenticate": "Bearer"})


def authenticate(db: Session, email: str, password: str) -> User | None:
    user = db.scalar(select(User).where(User.email == email))
    # a hash is verified in every outcome: the response time must not reveal
    # whether the e-mail is registered
    hashed = user.password_hash if user else DUMMY_HASH
    valid = password_hash.verify(password, hashed)
    return user if user and valid else None


@router.post("/login", response_model=Token)
def login(form: Annotated[OAuth2PasswordRequestForm, Depends()], db: SessionDep):
    user = authenticate(db, form.username, form.password)
    if user is None:
        # one text for every failure: no hint whether the e-mail exists
        raise unauthorized("Incorrect email or password")
    return Token(access_token=create_access_token(user.id))


def get_optional_user(
    token: Annotated[str | None, Depends(oauth2_scheme)], db: SessionDep
) -> User | None:
    if token is None:
        return None  # anonymous: the caller decides whether that is acceptable
    try:
        user_id = read_access_token(token)
    except jwt.InvalidTokenError:
        raise unauthorized("Invalid or expired token") from None
    # the user (and so the role) comes from the database on every request
    user = db.get(User, user_id)
    if user is None:
        raise unauthorized("Invalid or expired token")
    return user


def get_current_user(user: Annotated[User | None, Depends(get_optional_user)]) -> User:
    if user is None:
        raise unauthorized("Not authenticated")
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]
