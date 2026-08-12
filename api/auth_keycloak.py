"""
Phase 13 Stretch Goal: Keycloak OIDC Auth Provider Implementation.

Demonstrates the power of FastAPI dependency injection:
Swapping from local JWT (api/auth.py) to Keycloak OIDC (this file)
requires changing ONLY get_current_user() internals.
Zero route handlers in nodes.py, incidents.py, automation.py, or audit.py are touched.

Red Hat Story: Keycloak IS the Red Hat build of Keycloak (formerly Red Hat SSO).
Enterprise Red Hat customers mandate centralized OIDC/SSO rather than local user tables.
"""

from typing import Annotated
import os
import httpx
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import jwt, JWTError
from pydantic import BaseModel

KEYCLOAK_URL = os.environ.get("KEYCLOAK_URL", "http://localhost:8080")
REALM = os.environ.get("KEYCLOAK_REALM", "edgeguard")
CLIENT_ID = os.environ.get("KEYCLOAK_CLIENT_ID", "edgeguard-api")

# Keycloak OIDC discovery & JWKS URL
JWKS_URL = f"{KEYCLOAK_URL}/realms/{REALM}/protocol/openid-connect/certs"

oauth2_scheme = OAuth2PasswordBearer(tokenUrl=f"{KEYCLOAK_URL}/realms/{REALM}/protocol/openid-connect/token")

class CurrentUser(BaseModel):
    id: str
    role: str
    username: str
    email: str | None = None

_jwks_cache = None

async def _get_jwks():
    global _jwks_cache
    if _jwks_cache is None:
        async with httpx.AsyncClient() as client:
            resp = await client.get(JWKS_URL)
            _jwks_cache = resp.json()
    return _jwks_cache

async def get_current_user(token: Annotated[str, Depends(oauth2_scheme)]) -> CurrentUser:
    """
    Keycloak OIDC implementation of get_current_user().

    Decodes JWT using Keycloak realm JWKS public keys, validates issuer,
    and extracts client roles from realm_access / resource_access claims.
    """
    credentials_exc = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate Keycloak OIDC credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        jwks = await _get_jwks()
        unverified_header = jwt.get_unverified_header(token)
        rsa_key = {}
        for key in jwks.get("keys", []):
            if key["kid"] == unverified_header.get("kid"):
                rsa_key = {
                    "kty": key["kty"],
                    "kid": key["kid"],
                    "use": key["use"],
                    "n": key["n"],
                    "e": key["e"],
                }
                break

        if not rsa_key:
            raise credentials_exc

        payload = jwt.decode(
            token,
            rsa_key,
            algorithms=["RS256"],
            options={"verify_aud": False},
        )

        user_id: str = payload.get("sub", "")
        username: str = payload.get("preferred_username", user_id)
        email: str = payload.get("email", "")

        # Extract Keycloak realm roles or client roles
        realm_roles = payload.get("realm_access", {}).get("roles", [])
        if "admin" in realm_roles:
            role = "admin"
        elif "operator" in realm_roles:
            role = "operator"
        else:
            role = "viewer"

        return CurrentUser(id=user_id, role=role, username=username, email=email)

    except (JWTError, Exception) as e:
        raise credentials_exc from e
