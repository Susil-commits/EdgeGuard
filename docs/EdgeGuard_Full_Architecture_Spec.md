# EdgeGuard — Full Architecture & Build Spec
*Written so a coding agent (or you) can execute it phase-by-phase without needing to infer intent.*

---

## 1. Unique feature — the Red Hat-relevant differentiator

Everything in the base design (thresholds → incident → Ansible playbook) is a good foundation, but it's generic monitoring. The feature below is what makes it read as **"understands how Red Hat customers actually run automation,"** not "built a Nagios clone."

### 1a. Problem
Threshold-only remediation is always *reactive* — the disk is already full, the service has already died, before anything happens. It's also usually wired with brittle if/else logic buried in application code, which means every new remediation rule requires a code deploy. Red Hat's real hybrid/edge customers solve both problems with two specific, named patterns:
- **Event-Driven Ansible (EDA)** — rulebooks (declarative YAML, not code) that subscribe to event sources and trigger playbooks automatically, decoupling "what to watch for" from "how to fix it."
- **Predictive/trend-based alerting** (the pattern behind Red Hat Insights) — flag problems *before* they cross a hard threshold, using trend data, not just instantaneous values.

### 1b. Solution — build both, small but real
1. **Trend-based predictive detector**: alongside your existing hard-threshold rules, add an EWMA (exponentially weighted moving average) or simple linear-regression forecaster per metric. If disk usage is climbing at a rate that projects a threshold breach within a configurable horizon (e.g. 6 hours), raise a `predictive` severity incident *before* the hard threshold is crossed. This is a small, well-scoped ML-adjacent feature — not a research project.
2. **Real Event-Driven Ansible integration**: instead of your Python rule engine calling the Ansible runner directly, route the "safe to remediate" decision through an actual `ansible-rulebook` (the open-source EDA engine Red Hat ships as part of Ansible Automation Platform 2). EdgeGuard's API exposes a webhook event source; the rulebook watches it and triggers the playbook run itself. This means: **new remediation rules become YAML rulebook edits, not application redeploys** — genuinely matches how enterprises operate this in production, and gives you a concrete, correct thing to say when asked "have you used Ansible Automation Platform / EDA?"

### 1c. Where this lives in the architecture
```
Rule engine (Python, in-process)  → hard threshold + predictive incidents (existing)
                ↓ incident created → published to an internal event bus (Redis pub/sub or a simple webhook POST)
ansible-rulebook (separate process, real Red Hat OSS tool)
                ↓ matches condition in rulebook.yml
                → runs playbook via ansible-runner
                ↓ result posted back to EdgeGuard API (/v1/automation/jobs callback)
```
Keep your Python rule engine for detection (it owns thresholds + prediction). Hand off *only* the "should this trigger automation" decision to EDA. This split is intentional and defensible in an interview: detection logic stays testable Python; the automation trigger layer is the part enterprises want declarative and swappable.

---

## 2. Component architecture (full)

| Component | Responsibility | Tech |
|---|---|---|
| `agent` | Collect host metrics, buffer locally, send telemetry | Python 3.12, psutil, SQLite spool |
| `api` | REST endpoints, auth, RBAC, request validation | FastAPI, Pydantic |
| `worker` | Async processing: telemetry ingestion, rule evaluation, predictive forecasting | Python, Redis/RQ or Celery |
| `rule-engine` (inside worker) | Threshold + EWMA/regression forecasting, fingerprinting, incident lifecycle | Python |
| `event-bus` | Decouples incident creation from automation trigger | Redis pub/sub (simplest) |
| `eda-runner` | `ansible-rulebook` process watching the event bus / webhook | ansible-rulebook (Red Hat OSS) |
| `automation` | Ansible roles/playbooks, invoked by EDA or directly for testing | Ansible Core |
| `web` | Fleet/incident/automation dashboards | React + TypeScript |
| `db` | Durable state | PostgreSQL |
| `observability` | Metrics/logs/traces | Prometheus, OpenTelemetry, Grafana |

### Data flow (end to end)
```
[Edge node]
  agent (psutil) → local SQLite spool → HTTPS POST /v1/telemetry (retry w/ backoff)
        ↓
[API] validates → writes to Postgres `metrics` table → enqueues evaluation job
        ↓
[Worker: rule-engine]
  - threshold check (existing)
  - EWMA/regression check (new) → if trend breach projected, create `severity=predictive` incident
  - fingerprint dedupe: (node_id, rule_id) → reuse open incident or create new
        ↓ incident created/updated
[event-bus] incident event published
        ↓
[eda-runner: ansible-rulebook]
  rulebook condition matches (e.g. incident.severity in [critical, predictive] AND incident.rule == "service_inactive")
        ↓
  runs playbook via ansible-runner against target node (from allow-listed playbook registry)
        ↓
[Ansible target node] remediation applied, idempotent
        ↓
[API callback] /v1/automation/jobs/{id}/result → worker re-checks real health signal
        ↓
  incident resolved (only if verified healthy) OR escalated
        ↓
[audit_events] every step logged: who/what triggered it, what ran, what the result was
```

---

## 3. Repository structure
```
edgeguard/
  agent/
    collector.py          # psutil-based metric collection
    spool.py               # local SQLite durable buffer
    sender.py               # HTTPS client w/ retry+backoff
    service/edgeguard-agent.service   # systemd unit
  api/
    main.py
    routers/nodes.py, telemetry.py, incidents.py, automation.py, audit.py
    auth.py                # JWT-based auth, RBAC dependency
    models.py               # SQLAlchemy models
    schemas.py              # Pydantic request/response models
    db.py
  worker/
    tasks/ingest.py         # telemetry → metrics table
    tasks/evaluate.py        # rule engine entrypoint
    rules/threshold.py
    rules/predictive.py      # EWMA/regression forecaster (new)
    rules/fingerprint.py
    eventbus.py              # publish incident events
  eda/
    rulebooks/remediation.yml   # ansible-rulebook rulebook
    inventory/hosts.yml
  automation/
    roles/linux_baseline/
    roles/service_restart/
    roles/disk_cleanup/
    roles/container_restart/
    playbooks/*.yml
    ALLOWED_PLAYBOOKS.py       # allow-list enforced by API before any job runs
  web/
    src/pages/Fleet.tsx, Incidents.tsx, Automation.tsx, Audit.tsx
  infra/
    docker-compose.yml
    k8s/ (Deployments, Services, ConfigMaps, Secrets, NetworkPolicy)
  tests/
    unit/, integration/, e2e/
  docs/
    architecture.md, threat-model.md, runbooks/
  .github/workflows/ci.yml
```

---

## 4. Database schema (exact)
```sql
nodes(
  id UUID PK, hostname TEXT, site TEXT, environment TEXT,
  os TEXT, agent_version TEXT, status TEXT, last_seen TIMESTAMPTZ
)

metrics(
  id BIGSERIAL PK, node_id UUID FK, timestamp TIMESTAMPTZ,
  metric_name TEXT, value DOUBLE PRECISION, labels JSONB
)
-- INDEX (node_id, timestamp), INDEX (metric_name, timestamp)

incidents(
  id UUID PK, node_id UUID FK, fingerprint TEXT, severity TEXT,
  -- severity: 'predictive' | 'warning' | 'critical'
  state TEXT, rule TEXT, occurrence_count INT DEFAULT 1,
  created_at TIMESTAMPTZ, resolved_at TIMESTAMPTZ
)
-- UNIQUE partial index on (fingerprint) WHERE state = 'open'  -- enforces dedupe at DB level

automation_jobs(
  id UUID PK, incident_id UUID FK, playbook TEXT, status TEXT,
  triggered_by TEXT, -- 'eda' | 'manual'
  started_at TIMESTAMPTZ, finished_at TIMESTAMPTZ, result JSONB
)

audit_events(
  id BIGSERIAL PK, actor_id TEXT, action TEXT, resource_type TEXT,
  resource_id TEXT, result TEXT, timestamp TIMESTAMPTZ
)
```

---

## 5. API contract (representative subset — build the rest following this shape)

```
POST /v1/nodes/register
  → { hostname, site, environment, os }
  ← 201 { id, status: "registered" }

POST /v1/telemetry
  → { node_id, timestamp, metrics: [{name, value, labels}], event_id }
  ← 202 { accepted: true }   # idempotent on event_id

GET /v1/incidents?state=open&severity=critical
  ← [ { id, node_id, rule, severity, state, occurrence_count, created_at } ]

POST /v1/incidents/{id}/resolve
  → { resolution_note }
  ← 200 { id, state: "resolved" }   # only allowed if verification check passed — enforce server-side, not trusted from caller

POST /v1/automation/jobs
  → { incident_id, playbook, params, triggered_by: "eda" }
  ← 201 { id, status: "queued" }
  # SERVER-SIDE: reject if `playbook` not in ALLOWED_PLAYBOOKS registry — 403

POST /v1/automation/jobs/{id}/result   # callback from ansible-runner
  → { status, output, health_verified: bool }
  ← 200 { id, status: "recorded" }
```

---

## 6. EDA rulebook (concrete example — the unique feature, made real)
```yaml
# eda/rulebooks/remediation.yml
- name: EdgeGuard remediation
  hosts: all
  sources:
    - ansible.eda.webhook:
        host: 0.0.0.0
        port: 5000
  rules:
    - name: restart inactive service
      condition: event.severity == "critical" and event.rule == "service_inactive"
      action:
        run_playbook:
          name: automation/playbooks/restart_service.yml
          extra_vars:
            target_node: "{{ event.node_id }}"
            service_name: "{{ event.metadata.service_name }}"

    - name: predictive disk warning — pre-emptive cleanup
      condition: event.severity == "predictive" and event.rule == "disk_trend"
      action:
        run_playbook:
          name: automation/playbooks/disk_cleanup.yml
          extra_vars:
            target_node: "{{ event.node_id }}"
```
Run locally with: `ansible-rulebook --rulebook eda/rulebooks/remediation.yml -i eda/inventory/hosts.yml`. This is the literal command you'll demo live — it's a real, runnable Red Hat OSS component, not a simulation.

---

## 7. Predictive detector (concrete algorithm — keep it simple and explainable)
```python
# worker/rules/predictive.py
# EWMA-based trend projection — deliberately simple, deliberately explainable in an interview.
def project_breach(history: list[float], threshold: float, horizon_minutes: int) -> bool:
    if len(history) < 5:
        return False
    alpha = 0.3
    ewma = history[0]
    trend = 0.0
    for v in history[1:]:
        new_ewma = alpha * v + (1 - alpha) * ewma
        trend = new_ewma - ewma
        ewma = new_ewma
    projected = ewma + trend * horizon_minutes
    return projected >= threshold
```
Don't reach for a full ML library here — a defensible, explainable EWMA projection is exactly the right scope, and you should be able to derive/explain this formula from memory in an interview.

---

## 8. Build phases (agent-executable, in order — each ends with a working, tested increment)

1. **Skeleton**: FastAPI + Postgres + Docker Compose + GitHub Actions CI (lint+test+build+push to ghcr.io) on an empty app. *Done when:* CI is green and `docker compose up` serves `/health`.
2. **Node registration + telemetry ingestion**: `nodes`, `metrics` tables; `/v1/nodes/register`, `/v1/telemetry`. *Done when:* a curl POST creates a node and a metric row.
3. **Agent**: `collector.py` + `sender.py`, no spool yet. *Done when:* agent running on the Oracle VM successfully posts real psutil metrics to the API.
4. **Local spool + resilience**: SQLite buffer, retry/backoff. *Done when:* blocking outbound traffic on the VM causes spool growth, and unblocking causes replay with zero duplicate rows (verify via `event_id` uniqueness).
5. **Rule engine — threshold + fingerprint**: `incidents` table, threshold rules, dedupe. *Done when:* killing a systemd service produces exactly one open incident, not a flood.
6. **Rule engine — predictive**: EWMA forecaster wired in. *Done when:* a synthetic disk-fill script produces a `predictive` severity incident before the hard threshold is hit.
7. **Ansible automation layer**: roles, `ALLOWED_PLAYBOOKS` registry, `/v1/automation/jobs`. *Done when:* manually POSTing a job restarts a service on the target VM and the API records the result.
8. **Event-Driven Ansible integration**: event bus, rulebook, EDA running as its own process. *Done when:* killing a service end-to-end triggers detection → event bus → rulebook match → playbook run → verified resolution, with zero manual API calls.
9. **Kubernetes deployment**: containerize api/worker, deploy to kind/minikube with probes, resource limits, NetworkPolicy. *Done when:* a bad image fails readiness and never receives traffic.
10. **Observability**: Prometheus metrics, Grafana dashboard (fleet health, MTTR, remediation success rate). *Done when:* dashboard reflects a live-triggered incident within one scrape interval.
11. **Web dashboard**: minimal React views for the 4 pages above. *Done when:* you can demo the whole flow visually, not just via curl/logs.
12. **Hardening + demo recording**: RBAC roles enforced on every write route, audit log complete, threat-model doc written, 3–5 min recorded walkthrough covering: service-kill remediation, predictive-disk demo, WAN-outage buffering, and the EDA rulebook running live.

---

## 9. Definition of done
- [ ] `docker compose up` works from a clean clone
- [ ] CI green on every push
- [ ] Agent runs as a real systemd service on the Oracle VM
- [ ] EDA rulebook runs live and triggers a real playbook
- [ ] Predictive incident demonstrably fires before a threshold breach
- [ ] Every write endpoint has an audit_events row
- [ ] README has architecture diagram + honest "what's built vs. designed-only" section
- [ ] Recorded demo covers all 4 failure scenarios from the original design doc
