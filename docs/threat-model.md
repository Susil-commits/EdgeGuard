# EdgeGuard Threat Model & Security Specification

## 1. Overview
EdgeGuard processes telemetry from hybrid edge hosts and triggers automated remediation playbooks on remote nodes. Security is designed with defense-in-depth across authentication, authorization, playbook execution boundaries, and event pipeline security.

---

## 2. Threat Matrix & Mitigations

| Threat | Risk Level | Vector | Mitigation Strategy |
|---|---|---|---|
| **Unauthorized Playbook Execution** | High | Attacker triggers arbitrary root commands on edge nodes | **Server-side `ALLOWED_PLAYBOOKS` registry** enforces explicit allow-list. Any attempt to invoke unlisted playbooks yields a 403 Forbidden before execution. |
| **Agent Telemetry Spoofing / Replay** | Medium | Malicious entity sends fake metric spikes or replays captured telemetry | **Idempotent event ingestion** via unique `event_id` enforcement in Postgres. Shared agent bearer tokens validated on ingress. |
| **EDA Webhook Event Forgery** | Medium | Attacker POSTs fake incident payload directly to `ansible-rulebook` port 5000 | Webhook network policy restricts ingress to internal API/Worker subnets. Token headers validated by rulebook condition. |
| **Privilege Escalation via API** | High | Viewer user attempts manual incident resolution or playbook dispatch | **RBAC Dependency Enforcement** via `require_role("operator")` on all write routes. Zero bypass possible at router layer. |
| **Audit Trail Manipulation** | High | Operator attempts to conceal unauthorized manual remediation | Audit events written asynchronously to append-only Postgres `audit_events` table with explicit `actor_id` and timestamp. |

---

## 3. Playbook Allow-List Architecture
The server-side allow-list is defined in `automation/allowed_playbooks.py`:

```python
ALLOWED_PLAYBOOKS: dict[str, str] = {
    "restart_service": "automation/playbooks/restart_service.yml",
    "disk_cleanup": "automation/playbooks/disk_cleanup.yml",
    "container_restart": "automation/playbooks/container_restart.yml",
    "linux_baseline": "automation/playbooks/linux_baseline.yml",
}
```

Every call to `POST /v1/automation/jobs` validates the requested playbook against this registry prior to queueing an Ansible runner job.
