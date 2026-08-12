import React, { useEffect, useState } from 'react';
import { api, getRole } from '../api';
import { Incident } from '../types';
import { AlertTriangle, Zap, CheckCircle2, Filter } from 'lucide-react';

export const IncidentsPage: React.FC = () => {
  const [incidents, setIncidents] = useState<Incident[]>([]);
  const [loading, setLoading] = useState(true);
  const [severityFilter, setSeverityFilter] = useState<string>('');
  const [stateFilter, setStateFilter] = useState<string>('open');
  const [error, setError] = useState<string | null>(null);
  const [actionId, setActionId] = useState<string | null>(null);

  const role = getRole();

  const loadIncidents = async () => {
    try {
      const data = await api.getIncidents(stateFilter || undefined, severityFilter || undefined);
      setIncidents(data);
    } catch (err: any) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadIncidents();
    const interval = setInterval(loadIncidents, 5000);
    return () => clearInterval(interval);
  }, [stateFilter, severityFilter]);

  const handleAcknowledge = async (id: string) => {
    try {
      setActionId(id);
      await api.acknowledgeIncident(id);
      await loadIncidents();
    } catch (err: any) {
      setError(err.message);
    } finally {
      setActionId(null);
    }
  };

  const handleResolve = async (id: string) => {
    try {
      setActionId(id);
      await api.resolveIncident(id, 'Manually resolved via web dashboard operator action');
      await loadIncidents();
    } catch (err: any) {
      setError(err.message);
    } finally {
      setActionId(null);
    }
  };

  return (
    <div>
      <div className="page-header">
        <div>
          <h1 className="page-title">
            <AlertTriangle size={28} color="#f59e0b" />
            Incident Stream & Predictive Alarms
          </h1>
          <p className="page-subtitle">
            Threshold breaches and EWMA trend projections. Operator resolution writes to Audit Trail.
          </p>
        </div>

        <div style={{ display: 'flex', gap: '0.75rem', alignItems: 'center' }}>
          <Filter size={16} color="var(--text-muted)" />
          <select
            className="form-select"
            value={stateFilter}
            onChange={(e) => setStateFilter(e.target.value)}
            style={{ width: '130px' }}
          >
            <option value="">All States</option>
            <option value="open">Open</option>
            <option value="acknowledged">Acknowledged</option>
            <option value="resolved">Resolved</option>
          </select>

          <select
            className="form-select"
            value={severityFilter}
            onChange={(e) => setSeverityFilter(e.target.value)}
            style={{ width: '150px' }}
          >
            <option value="">All Severities</option>
            <option value="predictive">Predictive</option>
            <option value="warning">Warning</option>
            <option value="critical">Critical</option>
          </select>
        </div>
      </div>

      {error && (
        <div className="error-banner">
          {error}
        </div>
      )}

      <div className="card">
        <div className="table-wrapper">
          <table className="data-table">
            <thead>
              <tr>
                <th>Severity</th>
                <th>Rule Name</th>
                <th>State</th>
                <th>Node ID</th>
                <th>Occurrence Count</th>
                <th>Created At</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {loading ? (
                <tr><td colSpan={7} style={{ textAlign: 'center', padding: '2rem' }}>Loading incidents...</td></tr>
              ) : incidents.length === 0 ? (
                <tr><td colSpan={7} style={{ textAlign: 'center', padding: '2rem' }}>No incidents matching active filters.</td></tr>
              ) : (
                incidents.map((inc) => (
                  <tr key={inc.id} style={inc.severity === 'predictive' ? { background: 'rgba(139, 92, 246, 0.04)' } : {}}>
                    <td>
                      <span className={`badge badge-${inc.severity}`}>
                        {inc.severity === 'predictive' && <Zap size={12} />}
                        {inc.severity}
                      </span>
                    </td>
                    <td>
                      <div className="mono" style={{ fontWeight: 600 }}>{inc.rule}</div>
                      <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }} className="mono">{inc.fingerprint.substring(0, 16)}...</div>
                    </td>
                    <td>
                      <span className="badge badge-manual">{inc.state}</span>
                    </td>
                    <td className="mono" style={{ fontSize: '0.8rem' }}>{inc.node_id}</td>
                    <td>
                      <span style={{ fontWeight: 700, padding: '0.2rem 0.6rem', borderRadius: 4, background: 'var(--bg-card)' }}>
                        {inc.occurrence_count}x
                      </span>
                    </td>
                    <td className="mono" style={{ fontSize: '0.85rem' }}>
                      {new Date(inc.created_at).toLocaleString()}
                    </td>
                    <td>
                      {inc.state !== 'resolved' ? (
                        <div style={{ display: 'flex', gap: '0.4rem' }}>
                          {inc.state === 'open' && (
                            <button
                              className="btn btn-secondary"
                              style={{ padding: '0.3rem 0.6rem', fontSize: '0.75rem' }}
                              disabled={role === 'viewer' || actionId === inc.id}
                              onClick={() => handleAcknowledge(inc.id)}
                            >
                              Ack
                            </button>
                          )}
                          <button
                            className="btn btn-secondary"
                            style={{ padding: '0.3rem 0.6rem', fontSize: '0.75rem' }}
                            disabled={role === 'viewer' || actionId === inc.id}
                            onClick={() => handleResolve(inc.id)}
                          >
                            <CheckCircle2 size={12} />
                            Resolve
                          </button>
                        </div>
                      ) : (
                        <span style={{ fontSize: '0.8rem', color: 'var(--accent-emerald)', display: 'flex', alignItems: 'center', gap: '0.2rem' }}>
                          <CheckCircle2 size={14} /> Resolved
                        </span>
                      )}
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
