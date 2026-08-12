import React, { useState } from 'react';
import { FleetPage } from './pages/Fleet';
import { IncidentsPage } from './pages/Incidents';
import { AutomationPage } from './pages/Automation';
import { AuditPage } from './pages/Audit';
import { getRole, setAuthToken } from './api';
import { Role } from './types';
import { Shield, Server, AlertTriangle, Cpu, ScrollText, UserCheck } from 'lucide-react';

type Tab = 'fleet' | 'incidents' | 'automation' | 'audit';

export const App: React.FC = () => {
  const [activeTab, setActiveTab] = useState<Tab>('fleet');
  const [role, setRole] = useState<Role>(getRole());

  const handleRoleChange = (newRole: Role) => {
    setRole(newRole);
    setAuthToken(`demo-token-${newRole}`, newRole);
  };

  return (
    <div>
      <header className="app-header">
        <div className="brand">
          <Shield size={24} color="#ee0000" />
          EdgeGuard
          <span className="brand-badge">Red Hat Ansible EDA</span>
        </div>

        <nav className="nav-tabs">
          <button
            className={`nav-btn ${activeTab === 'fleet' ? 'active' : ''}`}
            onClick={() => setActiveTab('fleet')}
          >
            <Server size={16} />
            Fleet View
          </button>

          <button
            className={`nav-btn ${activeTab === 'incidents' ? 'active' : ''}`}
            onClick={() => setActiveTab('incidents')}
          >
            <AlertTriangle size={16} />
            Incidents & EWMA
          </button>

          <button
            className={`nav-btn ${activeTab === 'automation' ? 'active' : ''}`}
            onClick={() => setActiveTab('automation')}
          >
            <Cpu size={16} />
            Ansible Remediation
          </button>

          <button
            className={`nav-btn ${activeTab === 'audit' ? 'active' : ''}`}
            onClick={() => setActiveTab('audit')}
          >
            <ScrollText size={16} />
            Audit Log
          </button>
        </nav>

        <div className="role-switcher">
          <UserCheck size={16} />
          <span>Active Role:</span>
          <select
            className="role-select"
            value={role}
            onChange={(e) => handleRoleChange(e.target.value as Role)}
          >
            <option value="viewer">Viewer (Read Only)</option>
            <option value="operator">Operator (Action Permission)</option>
            <option value="admin">Admin (Full Control)</option>
          </select>
        </div>
      </header>

      <main className="container">
        {activeTab === 'fleet' && <FleetPage />}
        {activeTab === 'incidents' && <IncidentsPage />}
        {activeTab === 'automation' && <AutomationPage />}
        {activeTab === 'audit' && <AuditPage />}
      </main>
    </div>
  );
};
