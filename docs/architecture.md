# EdgeGuard Architecture & System Specification

## 1. High-Level Architecture

EdgeGuard decouples telemetry collection, predictive detection, event-driven remediation, and audit logging into a modular micro-service architecture.

```mermaid
graph TD
    Agent["Edge Agent (psutil + SQLite Spool)"] -->|HTTPS POST /v1/telemetry| API["EdgeGuard API (FastAPI)"]
    API -->|Async Write| DB[(PostgreSQL 16)]
    API -->|Enqueue Evaluation| Redis[(Redis Queue / PubSub)]
    
    Worker["Rule Engine Worker"] -->|Poll Jobs| Redis
    Worker -->|Fetch Metric History| DB
    Worker -->|Evaluate EWMA & Thresholds| Worker
    Worker -->|Create / Escalate Incident| DB
    Worker -->|Publish Event| Redis
    Worker -->|POST Webhook| EDA["EDA Runner (ansible-rulebook)"]
    
    EDA -->|Match Condition| Playbook["Ansible Playbook Run"]
    Playbook -->|SSH / Sudo| EdgeNode["Target Edge Node"]
    Playbook -->|Callback /v1/automation/jobs/id/result| API
    
    Web["React Web Dashboard"] -->|REST / JWT| API
    Prom["Prometheus"] -->|Scrape /metrics| API
```

---

## 2. End-to-End Self-Healing Remediation Cycle

```mermaid
sequenceDiagram
    autonumber
    participant Node as Target Node / VM
    participant Agent as Edge Agent
    participant API as EdgeGuard API
    participant Worker as Rule Engine
    participant EDA as Event-Driven Ansible
    participant DB as PostgreSQL

    Node->>Agent: Metric drop / service failure
    Agent->>API: POST /v1/telemetry (batch + event_id)
    API->>DB: Upsert metrics (idempotent)
    API->>Worker: Enqueue evaluation job
    Worker->>Worker: Check threshold & EWMA predictive projection
    Worker->>DB: Create Incident (deduped via sha256 fingerprint)
    Worker->>EDA: POST Webhook event payload
    EDA->>EDA: Evaluate remediation.yml rulebook
    EDA->>Node: Run ansible-runner playbook (e.g. restart_service.yml)
    Node-->>EDA: Remediation complete & health verified
    EDA->>API: POST /v1/automation/jobs/{id}/result
    API->>DB: Auto-resolve incident & record AuditEvent
```

---

## 3. Mathematical Extrapolation & Deduplication

### EWMA Forecasting Formula
$$EWMA_t = \alpha \cdot X_t + (1 - \alpha) \cdot EWMA_{t-1} \quad (\alpha = 0.3)$$
$$\text{Projected Value } P = EWMA_t + (EWMA_t - EWMA_{t-1}) \times H_{minutes}$$

### Fingerprint Hashing Formula
$$\text{Fingerprint} = \text{SHA256}(\text{node\_id} + \text{":"} + \text{rule\_id})$$
Enforced by DB Index: `CREATE UNIQUE INDEX ix_incidents_open_fingerprint ON incidents(fingerprint) WHERE state = 'open';`

---

## 4. Security & Isolation Controls
- **`ALLOWED_PLAYBOOKS` Registry**: Reject execution requests for playbooks not explicitly allow-listed in application config (`api/routers/automation.py`).
- **RBAC Roles**: `viewer` (read-only), `operator` (trigger remediation), `admin` (full system management & node deletion).
