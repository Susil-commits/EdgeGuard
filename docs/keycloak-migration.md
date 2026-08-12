# Phase 13 Stretch Goal — Keycloak (Red Hat SSO) Migration Guide

## Why Keycloak?
Keycloak is **literally a Red Hat product** (Red Hat build of Keycloak, formerly Red Hat Single Sign-On / RHSSO). In enterprise Red Hat environments (OpenShift, Ansible Automation Platform, RHEL Satellite), local application user tables are prohibited — all authentication and RBAC must route through an OpenID Connect (OIDC) / SAML IdP.

---

## Clean Dependency Abstraction Architecture

In EdgeGuard, all routes rely on a single FastAPI dependency:

```python
# Any router (e.g. incidents.py)
@router.post("/incidents/{id}/resolve")
async def resolve_incident(
    incident_id: uuid.UUID,
    user: Annotated[CurrentUser, Depends(require_role("operator"))]
):
    ...
```

Because `require_role()` wraps `get_current_user()`, swapping from local JWT auth (`api/auth.py`) to Keycloak OIDC (`api/auth_keycloak.py`) involves **changing only one import** in `api/auth.py` or aliasing `get_current_user`:

```python
# api/auth.py (Keycloak mode)
from api.auth_keycloak import get_current_user, CurrentUser, require_role
```

**Zero lines of code in router files (`nodes.py`, `incidents.py`, `automation.py`, `audit.py`) are modified.**

---

## Running Keycloak locally with Docker Compose

```bash
# Spin up Keycloak 25 with dedicated Postgres database
docker compose -f docker-compose.yml -f infra/docker-compose.keycloak.yml up -d keycloak
```

Keycloak Admin Console will be available at `http://localhost:8080` (credentials: `admin` / `admin`).

### Realm Configuration Steps:
1. Create Realm: `edgeguard`.
2. Create Client: `edgeguard-api` (Access Type: `confidential` / `public` PKCE).
3. Create Client Roles: `viewer`, `operator`, `admin`.
4. Assign roles to users or groups.
