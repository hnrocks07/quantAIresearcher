import React, { useState } from 'react';
import { usePolling } from '../hooks/usePolling';
import { api } from '../api/client';
import {
  ResponsiveContainer, AreaChart, Area, XAxis, YAxis, Tooltip, CartesianGrid,
} from 'recharts';

export default function DataIngestion() {
  const { data: status, refresh } = usePolling(api.ingestStatus, 3000);
  const { data: profiles } = usePolling(api.profiles, 30000);
  const { data: assets } = usePolling(() => api.assets('limit=20'), 10000);
  const [profile, setProfile] = useState('nse_equity');
  const [errors, setErrors] = useState(null);

  const handleStart = async () => {
    await api.ingestStart(profile);
    refresh();
  };

  const handleStop = async () => {
    await api.ingestStop();
    refresh();
  };

  const showErrors = async () => {
    const errs = await api.ingestErrors();
    setErrors(errs);
  };

  const isRunning = status?.status === 'running';
  const progressPct = status?.progress_pct || 0;

  return (
    <div>
      <div className="grid grid-4">
        <div className="card">
          <h3>Status</h3>
          <div className="stat-value">
            <span className={`badge badge-${isRunning ? 'info' : status?.status === 'completed' ? 'success' : 'warning'}`}>
              {status?.status || 'idle'}
            </span>
          </div>
        </div>
        <div className="card">
          <h3>Progress</h3>
          <div className="stat-value">{progressPct.toFixed(1)}%</div>
          <div className="stat-label">{status?.processed || 0}/{status?.total_instruments || 0}</div>
        </div>
        <div className="card">
          <h3>Rows Inserted</h3>
          <div className="stat-value">{(status?.rows_inserted || 0).toLocaleString()}</div>
        </div>
        <div className="card">
          <h3>Errors</h3>
          <div className="stat-value" style={{color: (status?.errors_count || 0) > 0 ? 'var(--danger)' : 'var(--text)'}}>
            {status?.errors_count || 0}
          </div>
        </div>
      </div>

      <div className="card">
        <h3>Progress Bar</h3>
        <div style={{background: 'var(--border)', borderRadius: '8px', height: '24px', overflow: 'hidden'}}>
          <div style={{
            width: `${progressPct}%`, height: '100%',
            background: 'linear-gradient(90deg, #0d6efd, #198754)',
            transition: 'width 0.5s ease',
            borderRadius: '8px',
          }} />
        </div>
        <div style={{fontSize: '12px', color: 'var(--text-secondary)', marginTop: '4px'}}>
          Current: {status?.current_symbol || 'None'} | Elapsed: {Math.round((status?.elapsed_seconds || 0) / 60)}m
        </div>
      </div>

      <div className="card">
        <h3>Controls</h3>
        <div style={{display: 'flex', gap: '12px', alignItems: 'center'}}>
          <select value={profile} onChange={e => setProfile(e.target.value)}
                  style={{padding: '8px', borderRadius: '6px', border: '1px solid var(--border)', background: 'var(--card-bg)', color: 'var(--text)'}}>
            {(profiles || ['nse_equity', 'crypto']).map(p => (
              <option key={p} value={p}>{p}</option>
            ))}
          </select>
          {!isRunning ? (
            <button className="btn btn-primary" onClick={handleStart}>Start Ingestion</button>
          ) : (
            <button className="btn btn-danger" onClick={handleStop}>Stop</button>
          )}
          <button className="btn btn-sm" onClick={showErrors} style={{background: 'var(--border)', color: 'var(--text)'}}>
            Show Errors
          </button>
        </div>
      </div>

      <div className="card">
        <h3>Assets in Database (latest 20)</h3>
        <table>
          <thead>
            <tr><th>Symbol</th><th>Name</th><th>Type</th><th>Exchange</th><th>Currency</th></tr>
          </thead>
          <tbody>
            {(assets?.assets || []).map(a => (
              <tr key={a.id}>
                <td>{a.symbol}</td><td>{a.name}</td>
                <td>{a.asset_type}</td><td>{a.exchange}</td><td>{a.currency}</td>
              </tr>
            ))}
            {(!assets?.assets || assets.assets.length === 0) && (
              <tr><td colSpan="5" style={{textAlign: 'center', color: 'var(--text-secondary)'}}>No assets — run ingestion first</td></tr>
            )}
          </tbody>
        </table>
      </div>

      {errors && errors.length > 0 && (
        <div className="card" style={{borderColor: 'var(--danger)'}}>
          <h3>Recent Errors</h3>
          <table>
            <thead><tr><th>Symbol</th><th>Error</th><th>Time</th></tr></thead>
            <tbody>
              {errors.slice(0, 20).map((e, i) => (
                <tr key={i}>
                  <td>{e.symbol || 'System'}</td>
                  <td style={{color: 'var(--danger)', fontSize: '12px'}}>{e.error}</td>
                  <td style={{fontSize: '12px'}}>{e.timestamp || ''}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
