import React, { useEffect, useState } from 'react';
import { api, getRole } from '../api';
import { AutomationJob } from '../types';
import { Cpu, Play, CheckCircle2, XCircle, Clock, ShieldAlert } from 'lucide-react';

export const AutomationPage: React.FC = () => {
  const [jobs, setJobs] = useState<AutomationJob[]>([]);
  const [loading, setLoading] = useState(true);
  const [showModal, setShowModal] = useState(false);
  const [selectedPlaybook, setSelectedPlaybook] = useState('restart_service');
  const [incidentId, setIncidentId] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  const role = getRole();

  const loadJobs = async () => {
    try {
      const data = await api.getAutomationJobs();
      setJobs(data);
    } catch (err: any) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadJobs();
    const interval = setInterval(loadJobs, 5000);
    return () => clearInterval(interval);
  }, []);

  const handleTrigger = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      await api.triggerAutomation(selectedPlaybook, incidentId || undefined);
      setShowModal(false);
      await loadJobs();
    } catch (err: any) {
      setError(err.message);
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div>
      <div className="page-header">
        <div>
          <h1 className="page-title">
            <Cpu size={28} color="#06b6d4" />
            Ansible & EDA Remediation Engine
          </h1>
          <p className="page-subtitle">
            Self-healing automation jobs triggered declaratively by EDA rulebooks or manual operator dispatch
          </p>
        </div>

        <button
          className="btn"
          onClick={() => { setError(null); setShowModal(true); }}
        >
          <Play size={16} />
          Dispatch Playbook
        </button>
      </div>

      {error && !showModal && (
        <div className="error-banner">
          {error}
        </div>
      )}

      <div className="card">
        <div className="table-wrapper">
          <table className="data-table">
            <thead>
              <tr>
                <th>Status</th>
                <th>Playbook Name</th>
                <th>Trigger Source</th>
                <th>Linked Incident ID</th>
                <th>Started At</th>
                <th>Finished At</th>
                <th>Result / Health Verification</th>
              </tr>
            </thead>
            <tbody>
              {loading ? (
                <tr><td colSpan={7} style={{ textAlign: 'center', padding: '2rem' }}>Loading automation job logs...</td></tr>
              ) : jobs.length === 0 ? (
                <tr><td colSpan={7} style={{ textAlign: 'center', padding: '2rem' }}>No automation jobs executed yet.</td></tr>
              ) : (
                jobs.map((job) => (
                  <tr key={job.id}>
                    <td>
                      <span className={`badge ${job.status === 'success' ? 'badge-online' : job.status === 'failed' ? 'badge-critical' : 'badge-warning'}`}>
                        {job.status === 'success' ? <CheckCircle2 size={12} /> : job.status === 'failed' ? <XCircle size={12} /> : <Clock size={12} />}
                        {job.status}
                      </span>
                    </td>
                    <td>
                      <div className="mono" style={{ fontWeight: 600 }}>{job.playbook}</div>
                      <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }} className="mono">{job.id}</div>
                    </td>
                    <td>
                      <span className={`badge ${job.triggered_by === 'eda' ? 'badge-eda' : 'badge-manual'}`}>
                        {job.triggered_by === 'eda' ? 'EDA Rulebook' : 'Manual Dispatch'}
                      </span>
                    </td>
                    <td className="mono" style={{ fontSize: '0.8rem' }}>
                      {job.incident_id || 'N/A (Direct)'}
                    </td>
                    <td className="mono" style={{ fontSize: '0.85rem' }}>
                      {job.started_at ? new Date(job.started_at).toLocaleTimeString() : 'Queued'}
                    </td>
                    <td className="mono" style={{ fontSize: '0.85rem' }}>
                      {job.finished_at ? new Date(job.finished_at).toLocaleTimeString() : 'Running...'}
                    </td>
                    <td>
                      <div style={{ fontSize: '0.85rem', color: 'var(--text-secondary)' }}>
                        {job.result?.output || 'No output recorded'}
                      </div>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>

      {showModal && (
        <div className="modal-overlay" onClick={() => setShowModal(false)}>
          <div className="modal-content" onClick={(e) => e.stopPropagation()}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '1rem' }}>
              <ShieldAlert size={24} color="var(--accent-indigo)" />
              <h2 style={{ fontSize: '1.2rem', color: '#fff' }}>Dispatch Allowed Playbook</h2>
            </div>

            {error && (
              <div className="error-banner">
                {error}
              </div>
            )}

            <form onSubmit={handleTrigger}>
              <div className="form-group">
                <label className="form-label">Target Playbook (Server Allow-List)</label>
                <select
                  className="form-select"
                  value={selectedPlaybook}
                  onChange={(e) => setSelectedPlaybook(e.target.value)}
                >
                  <option value="restart_service">restart_service.yml</option>
                  <option value="disk_cleanup">disk_cleanup.yml</option>
                  <option value="container_restart">container_restart.yml</option>
                  <option value="unauthorized_script">unauthorized_script.yml (Triggers 403 Security Check)</option>
                </select>
              </div>

              <div className="form-group">
                <label className="form-label">Linked Incident ID (Optional)</label>
                <input
                  type="text"
                  className="form-input mono"
                  placeholder="e.g. inc-1001-predictive"
                  value={incidentId}
                  onChange={(e) => setIncidentId(e.target.value)}
                />
              </div>

              <div style={{ fontSize: '0.8rem', color: 'var(--text-muted)', marginBottom: '1.5rem' }}>
                Current Role: <strong>{role}</strong>. Requires <code>operator</code> or <code>admin</code> role.
              </div>

              <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '0.75rem' }}>
                <button
                  type="button"
                  className="btn btn-secondary"
                  onClick={() => setShowModal(false)}
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="btn"
                  disabled={submitting}
                >
                  {submitting ? 'Dispatching...' : 'Confirm Dispatch'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};
