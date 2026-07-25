import React, { useState } from 'react';
import { usePolling } from '../hooks/usePolling';
import { api } from '../api/client';
import { usePolling as usePoll } from '../hooks/usePolling';

export default function KillSwitch() {
  const { data: status, refresh } = usePolling(api.killSwitchStatus, 2000);
  const { data: events } = usePolling(() => api.events(50), 5000);
  const [reason, setReason] = useState('manual emergency');

  const handleTrigger = async () => {
    await api.killSwitchTrigger(reason);
    refresh();
  };

  const handleReset = async () => {
    await api.killSwitchReset();
    refresh();
  };

  const handleHeartbeat = async () => {
    await api.killSwitchHeartbeat();
    refresh();
  };

  const isActive = status?.is_active;

  return (
    <div>
      <div className="grid grid-3">
        <div className="card" style={{borderColor: isActive ? 'var(--danger)' : 'var(--success)', borderWidth: '2px'}}>
          <h3>Kill Switch</h3>
          <div className="stat-value" style={{fontSize: '36px', color: isActive ? 'var(--danger)' : 'var(--success)'}}>
            {isActive ? 'ACTIVE' : 'SAFE'}
          </div>
          <div className="stat-label">
            {status?.safe_to_trade ? 'Trading allowed' : 'ALL TRADING HALTED'}
          </div>
        </div>
        <div className="card">
          <h3>Triggered By</h3>
          <div className="stat-value" style={{fontSize: '18px'}}>{status?.triggered_by || 'None'}</div>
          <div className="stat-label">{status?.reason || ''}</div>
        </div>
        <div className="card">
          <h3>Last Heartbeat</h3>
          <div className="stat-value" style={{fontSize: '18px'}}>
            {status?.heartbeat_age != null ? `${status.heartbeat_age.toFixed(0)}s ago` : 'Never'}
          </div>
          <div className="stat-label">Timeout: {status?.heartbeat_timeout || 15}s</div>
        </div>
      </div>

      <div className="card">
        <h3>Controls</h3>
        <div style={{display: 'flex', gap: '12px', alignItems: 'center', flexWrap: 'wrap'}}>
          <input
            type="text" value={reason} onChange={e => setReason(e.target.value)}
            placeholder="Reason..."
            style={{padding: '8px 12px', borderRadius: '6px', border: '1px solid var(--border)', background: 'var(--card-bg)', color: 'var(--text)', width: '250px'}}
          />
          <button className="btn btn-danger" onClick={handleTrigger}
                  style={{fontSize: '16px', padding: '12px 24px'}}>
            TRIGGER KILL SWITCH
          </button>
          <button className="btn btn-success" onClick={handleReset}>Reset</button>
          <button className="btn btn-primary btn-sm" onClick={handleHeartbeat}>Send Heartbeat</button>
        </div>
      </div>

      <div className="card">
        <h3>Recent System Events</h3>
        <table>
          <thead>
            <tr><th>Time</th><th>Type</th><th>Source</th></tr>
          </thead>
          <tbody>
            {(events || []).slice(0, 30).map((e, i) => (
              <tr key={i}>
                <td style={{fontSize: '12px'}}>{e.timestamp || ''}</td>
                <td>
                  <span className={`badge badge-${e.event_type?.includes('kill') ? 'danger' : 'info'}`}>
                    {e.event_type}
                  </span>
                </td>
                <td>{e.source}</td>
              </tr>
            ))}
            {(!events || events.length === 0) && (
              <tr><td colSpan="3" style={{textAlign: 'center', color: 'var(--text-secondary)'}}>No events</td></tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
