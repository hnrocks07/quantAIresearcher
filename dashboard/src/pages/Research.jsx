import React, { useState } from 'react';
import { usePolling } from '../hooks/usePolling';
import { api } from '../api/client';
import {
  ResponsiveContainer, LineChart, Line, XAxis, YAxis, Tooltip, CartesianGrid,
} from 'recharts';

export default function Research() {
  const { data: status, refresh } = usePolling(api.researchStatus, 3000);
  const [profile, setProfile] = useState('nse_equity');
  const [topN, setTopN] = useState(50);
  const { data: profiles } = usePolling(api.profiles, 30000);

  const handleStart = async () => {
    await api.researchStart(profile, topN);
    refresh();
  };

  const handleStop = async () => {
    await api.researchStop();
    refresh();
  };

  const isRunning = status?.status === 'running';

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
          <h3>Strategies Tested</h3>
          <div className="stat-value">{status?.strategies_tested || 0}</div>
        </div>
        <div className="card">
          <h3>Shortlisted</h3>
          <div className="stat-value" style={{color: 'var(--success)'}}>{status?.strategies_shortlisted || 0}</div>
        </div>
        <div className="card">
          <h3>Backtests Run</h3>
          <div className="stat-value">{status?.backtests_run || 0}</div>
        </div>
      </div>

      <div className="card">
        <h3>Controls</h3>
        <div style={{display: 'flex', gap: '12px', alignItems: 'center', flexWrap: 'wrap'}}>
          <select value={profile} onChange={e => setProfile(e.target.value)}
                  style={{padding: '8px', borderRadius: '6px', border: '1px solid var(--border)', background: 'var(--card-bg)', color: 'var(--text)'}}>
            {(profiles || ['nse_equity', 'crypto']).map(p => (
              <option key={p} value={p}>{p}</option>
            ))}
          </select>
          <label style={{fontSize: '14px'}}>
            Top N assets:
            <input type="number" value={topN} onChange={e => setTopN(parseInt(e.target.value) || 50)}
                   style={{width: '60px', marginLeft: '6px', padding: '6px', borderRadius: '4px', border: '1px solid var(--border)', background: 'var(--card-bg)', color: 'var(--text)'}} />
          </label>
          {!isRunning ? (
            <button className="btn btn-primary" onClick={handleStart}>Start Research</button>
          ) : (
            <button className="btn btn-danger" onClick={handleStop}>Stop Research</button>
          )}
        </div>
      </div>

      <div className="grid grid-2">
        <div className="card">
          <h3>Current Work</h3>
          <div style={{fontSize: '14px', wordBreak: 'break-all'}}>{status?.current_work || 'Idle'}</div>
        </div>
        <div className="card">
          <h3>Elapsed</h3>
          <div className="stat-value">{Math.round((status?.elapsed_seconds || 0) / 60)}m</div>
          <div className="stat-label">{status?.errors_count || 0} errors</div>
        </div>
      </div>
    </div>
  );
}
