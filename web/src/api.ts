import { Node, Incident, AutomationJob, AuditEvent, Role } from './types';

const API_BASE = '/v1';

let authToken: string | null = localStorage.getItem('edgeguard_token');
let currentRole: Role = (localStorage.getItem('edgeguard_role') as Role) || 'operator';

export const setAuthToken = (token: string, role: Role) => {
  authToken = token;
  currentRole = role;
  localStorage.setItem('edgeguard_token', token);
  localStorage.setItem('edgeguard_role', role);
};

export const getRole = (): Role => currentRole;

const headers = () => ({
  'Content-Type': 'application/json',
  ...(authToken ? { Authorization: `Bearer ${authToken}` } : {}),
});

export const api = {
  async getNodes(): Promise<Node[]> {
    try {
      const res = await fetch(`${API_BASE}/nodes`, { headers: headers() });
      if (!res.ok) return mockNodes;
      return await res.json();
    } catch {
      return mockNodes;
    }
  },

  async getIncidents(state?: string, severity?: string): Promise<Incident[]> {
    try {
      const query = new URLSearchParams();
      if (state) query.append('state', state);
      if (severity) query.append('severity', severity);
      const res = await fetch(`${API_BASE}/incidents?${query.toString()}`, { headers: headers() });
      if (!res.ok) return mockIncidents;
      return await res.json();
    } catch {
      return mockIncidents;
    }
  },

  async acknowledgeIncident(id: string): Promise<void> {
    const res = await fetch(`${API_BASE}/incidents/${id}/acknowledge`, {
      method: 'POST',
      headers: headers(),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: 'Failed to acknowledge' }));
      throw new Error(err.detail || 'Acknowledge failed');
    }
  },

  async resolveIncident(id: string, note: string): Promise<void> {
    const res = await fetch(`${API_BASE}/incidents/${id}/resolve`, {
      method: 'POST',
      headers: headers(),
      body: JSON.stringify({ resolution_note: note }),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: 'Failed to resolve' }));
      throw new Error(err.detail || 'Resolution failed');
    }
  },

  async getAutomationJobs(): Promise<AutomationJob[]> {
    try {
      const res = await fetch(`${API_BASE}/automation/jobs`, { headers: headers() });
      if (!res.ok) return mockJobs;
      return await res.json();
    } catch {
      return mockJobs;
    }
  },

  async triggerAutomation(playbook: string, incidentId?: string): Promise<void> {
    const res = await fetch(`${API_BASE}/automation/jobs`, {
      method: 'POST',
      headers: headers(),
      body: JSON.stringify({
        playbook,
        incident_id: incidentId || null,
        triggered_by: 'manual',
      }),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: 'Failed to trigger job' }));
      throw new Error(err.detail || `HTTP ${res.status}: Forbidden / Allowed Playbooks check failed`);
    }
  },

  async getAuditEvents(): Promise<AuditEvent[]> {
    try {
      const res = await fetch(`${API_BASE}/audit`, { headers: headers() });
      if (!res.ok) return mockAudit;
      return await res.json();
    } catch {
      return mockAudit;
    }
  },
};

// Fallback Mock Data for standalone visual demo
const mockNodes: Node[] = [
  {
    id: 'f81d4fae-7dec-11d0-a765-00a0c91e6bf6',
    hostname: 'rhel-edge-node-01.lab.internal',
    site: 'Austin-Edge-DC1',
    environment: 'production',
    os: 'Red Hat Enterprise Linux 9.4',
    agent_version: 'v0.1.0',
    status: 'online',
    last_seen: new Date().toISOString(),
  },
  {
    id: 'a12b3c4d-5e6f-7a8b-9c0d-1e2f3a4b5c6d',
    hostname: 'oracle-vm-target.cloud.internal',
    site: 'Oracle-Cloud-OCI',
    environment: 'staging',
    os: 'Oracle Linux 9.2',
    agent_version: 'v0.1.0',
    status: 'online',
    last_seen: new Date(Date.now() - 12000).toISOString(),
  },
];

const mockIncidents: Incident[] = [
  {
    id: 'inc-1001-predictive',
    node_id: 'f81d4fae-7dec-11d0-a765-00a0c91e6bf6',
    fingerprint: 'e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855',
    severity: 'predictive',
    state: 'open',
    rule: 'disk_trend',
    occurrence_count: 3,
    created_at: new Date(Date.now() - 15 * 60000).toISOString(),
    resolved_at: null,
  },
  {
    id: 'inc-1002-critical',
    node_id: 'a12b3c4d-5e6f-7a8b-9c0d-1e2f3a4b5c6d',
    fingerprint: '8f434346648f6b96df89dda901c5176b10a6d83961dd3c1ac88b59b2dc327aa4',
    severity: 'critical',
    state: 'open',
    rule: 'service_inactive',
    occurrence_count: 1,
    created_at: new Date(Date.now() - 5 * 60000).toISOString(),
    resolved_at: null,
  },
];

const mockJobs: AutomationJob[] = [
  {
    id: 'job-901',
    incident_id: 'inc-1002-critical',
    playbook: 'restart_service',
    status: 'success',
    triggered_by: 'eda',
    started_at: new Date(Date.now() - 4 * 60000).toISOString(),
    finished_at: new Date(Date.now() - 3.8 * 60000).toISOString(),
    result: { output: 'Service restarted successfully via ansible-rulebook', health_verified: true },
  },
  {
    id: 'job-900',
    incident_id: 'inc-1001-predictive',
    playbook: 'disk_cleanup',
    status: 'success',
    triggered_by: 'manual',
    started_at: new Date(Date.now() - 12 * 60000).toISOString(),
    finished_at: new Date(Date.now() - 11 * 60000).toISOString(),
    result: { output: 'Journal vacuumed 420MB reclaimed', health_verified: true },
  },
];

const mockAudit: AuditEvent[] = [
  {
    id: 104,
    actor_id: 'eda',
    action: 'automation.job.create',
    resource_type: 'automation_job',
    resource_id: 'job-901',
    result: 'success',
    timestamp: new Date(Date.now() - 4 * 60000).toISOString(),
  },
  {
    id: 103,
    actor_id: 'operator_john',
    action: 'incident.resolve',
    resource_type: 'incident',
    resource_id: 'inc-1001-predictive',
    result: 'success',
    timestamp: new Date(Date.now() - 11 * 60000).toISOString(),
  },
];
