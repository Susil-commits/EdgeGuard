import React, { useEffect, useState } from 'react';
import { api } from '../api';
import { Node } from '../types';
import { Server, Activity, ShieldCheck, Clock } from 'lucide-react';

export const FleetPage: React.FC = () => {
  const [nodes, setNodes] = useState<Node[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const load = async () => {
      const data = await api.getNodes();
      setNodes(data);
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
            <Server size={28} color="#6366f1" />
            Edge Fleet Infrastructure
          </h1>
          <p className="page-subtitle">
            Observational health tracking across hybrid edge nodes and target VMs
          </p>
        </div>
        <div style={{ display: 'flex', gap: '1rem' }}>
          <div className="card" style={{ padding: '0.75rem 1.25rem', display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
            <Activity size={20} color="#10b981" />
            <div>
              <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>ACTIVE NODES</div>
              <div style={{ fontWeight: 700, fontSize: '1.1rem' }}>{nodes.filter(n => n.status === 'online').length} / {nodes.length}</div>
            </div>
          </div>
        </div>
      </div>

      <div className="card">
        <div className="table-wrapper">
          <table className="data-table">
            <thead>
              <tr>
                <th>Status</th>
                <th>Hostname</th>
                <th>Site / Location</th>
                <th>Environment</th>
                <th>OS Distribution</th>
                <th>Agent Version</th>
                <th>Last Heartbeat</th>
              </tr>
            </thead>
            <tbody>
              {loading ? (
                <tr><td colSpan={7} style={{ textAlign: 'center', padding: '2rem' }}>Loading node fleet data...</td></tr>
              ) : nodes.length === 0 ? (
                <tr><td colSpan={7} style={{ textAlign: 'center', padding: '2rem' }}>No nodes registered yet.</td></tr>
              ) : (
                nodes.map((node) => (
                  <tr key={node.id}>
                    <td>
                      <span className={`badge ${node.status === 'online' ? 'badge-online' : 'badge-offline'}`}>
                        <span style={{ width: 6, height: 6, borderRadius: '50%', background: 'currentColor' }}></span>
                        {node.status}
                      </span>
                    </td>
                    <td>
                      <div style={{ fontWeight: 600 }} className="mono">{node.hostname}</div>
                      <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }} className="mono">{node.id}</div>
                    </td>
                    <td>{node.site || 'Default Site'}</td>
                    <td>
                      <span className="badge badge-manual">{node.environment || 'production'}</span>
                    </td>
                    <td>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
                        <ShieldCheck size={14} color="#ee0000" />
                        {node.os || 'Linux'}
                      </div>
                    </td>
                    <td className="mono">{node.agent_version || 'v0.1.0'}</td>
                    <td className="mono" style={{ color: 'var(--text-secondary)' }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '0.3rem' }}>
                        <Clock size={12} />
                        {node.last_seen ? new Date(node.last_seen).toLocaleTimeString() : 'Never'}
                      </div>
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
