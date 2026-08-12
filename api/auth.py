"""
Auth dependency — all route code depends ONLY on get_current_user().

Design contract: this is the single boundary between "who is the caller" and
"what can they do". To migrate from local JWT to Keycloak OIDC (Phase 13),
replace ONLY the internals of get_current_user() — no route code changes.

Roles:
  viewer   — read-only access to all resources
  operator — viewer + resolve incidents + trigger automation jobs
  admin    — operator + node management + user management
"""

from datetime import UTC, datetime, timedelta
from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from pydantic import BaseModel

from api.config import settings

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/v1/auth/token")

ROLES_HIERARCHY = {"viewer": 0, "operator": 1, "admin": 2}


class TokenData(BaseModel):
    sub: str  # user id
    role: str
    exp: datetime


class CurrentUser(BaseModel):
    id: str
    role: str


def create_access_token(user_id: str, role: str) -> str:
    """Create a signed JWT for the given user and role."""
    expire = datetime.now(UTC) + timedelta(minutes=settings.JWT_EXPIRE_MINUTES)
    payload = {"sub": user_id, "role": role, "exp": expire}
    return jwt.encode(payload, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)


async def get_current_user(token: Annotated[str, Depends(oauth2_scheme)]) -> CurrentUser:
    """
    FastAPI dependency — decode and validate a JWT, return the current user.

    THIS IS THE ONLY FUNCTION THAT SHOULD CHANGE when migrating to Keycloak:
    swap jwt.decode() for an OIDC introspection / public-key validation call.
    """
    credentials_exc = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM])
        user_id = payload.get("sub")
        if user_id is None:
            raise credentials_exc
        role = payload.get("role", "viewer")
        return CurrentUser(id=user_id, role=role)
    except JWTError:
        raise credentials_exc


def require_role(minimum_role: str):
    """
    Dependency factory — raises 403 if the current user's role is below minimum_role.

    Usage:
        @router.post("/sensitive")
        async def endpoint(user: Annotated[CurrentUser, Depends(require_role("operator"))]):
            ...
    """

    async def checker(user: Annotated[CurrentUser, Depends(get_current_user)]) -> CurrentUser:
        if ROLES_HIERARCHY.get(user.role, -1) < ROLES_HIERARCHY.get(minimum_role, 999):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Role '{user.role}' does not have permission. Required: '{minimum_role}'.",
            )
        return user

    return checker
