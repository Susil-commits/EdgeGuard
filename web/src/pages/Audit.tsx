import React, { useEffect, useState } from 'react';
import { api } from '../api';
import { AuditEvent } from '../types';
import { ScrollText, UserCheck, Shield } from 'lucide-react';

export const AuditPage: React.FC = () => {
  const [events, setEvents] = useState<AuditEvent[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const load = async () => {
      const data = await api.getAuditEvents();
      setEvents(data);
      setLoading(false);
    };
    load();
    const interval = setInterval(load, 5000);
    return () => clearInterval(interval);
  }, []);

  return (
    <div>
      <div className="page-header">
        <div>
          <h1 className="page-title">
            <ScrollText size={28} color="#8b5cf6" />
            Compliance & System Audit Trail
          </h1>
          <p className="page-subtitle">
            Immutable log of all human operator decisions, automated EDA playbooks, and state changes
          </p>
        </div>
      </div>

      <div className="card">
        <div className="table-wrapper">
          <table className="data-table">
            <thead>
              <tr>
                <th>Event ID</th>
                <th>Actor ID</th>
                <th>Action</th>
                <th>Resource Type</th>
                <th>Resource ID</th>
                <th>Result</th>
                <th>Timestamp</th>
              </tr>
            </thead>
            <tbody>
              {loading ? (
                <tr><td colSpan={7} style={{ textAlign: 'center', padding: '2rem' }}>Loading compliance logs...</td></tr>
              ) : events.length === 0 ? (
                <tr><td colSpan={7} style={{ textAlign: 'center', padding: '2rem' }}>No audit events recorded yet.</td></tr>
              ) : (
                events.map((evt) => (
                  <tr key={evt.id}>
                    <td className="mono">#{evt.id}</td>
                    <td>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem', fontWeight: 600 }}>
                        {evt.actor_id === 'eda' ? (
                          <Shield size={14} color="var(--accent-cyan)" />
                        ) : (
                          <UserCheck size={14} color="var(--accent-purple)" />
                        )}
                        {evt.actor_id}
                      </div>
                    </td>
                    <td className="mono" style={{ color: 'var(--accent-indigo)', fontWeight: 500 }}>
                      {evt.action}
                    </td>
                    <td>
                      <span className="badge badge-manual">{evt.resource_type || 'system'}</span>
                    </td>
                    <td className="mono" style={{ fontSize: '0.85rem' }}>
                      {evt.resource_id || 'N/A'}
                    </td>
                    <td>
                      <span className={`badge ${evt.result === 'success' ? 'badge-online' : 'badge-critical'}`}>
                        {evt.result}
                      </span>
                    </td>
                    <td className="mono" style={{ fontSize: '0.85rem' }}>
                      {new Date(evt.timestamp).toLocaleString()}
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
};
