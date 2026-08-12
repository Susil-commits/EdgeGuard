export interface Node {
  id: string;
  hostname: string;
  site: string | null;
  environment: string | null;
  os: string | null;
  agent_version: string | null;
  status: 'registered' | 'online' | 'offline';
  last_seen: string | null;
}

export interface Incident {
  id: string;
  node_id: string;
  fingerprint: string;
  severity: 'predictive' | 'warning' | 'critical';
  state: 'open' | 'acknowledged' | 'resolved';
  rule: string;
  occurrence_count: number;
  created_at: string;
  resolved_at: string | null;
}

export interface AutomationJob {
  id: string;
  incident_id: string | null;
  playbook: string;
  status: 'queued' | 'running' | 'success' | 'failed';
  triggered_by: 'eda' | 'manual';
  started_at: string | null;
  finished_at: string | null;
  result: Record<string, any> | null;
}

export interface AuditEvent {
  id: number;
  actor_id: string;
  action: string;
  resource_type: string | null;
  resource_id: string | null;
  result: string;
  timestamp: string;
}

export type Role = 'viewer' | 'operator' | 'admin';
