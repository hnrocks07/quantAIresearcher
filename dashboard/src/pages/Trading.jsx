import React from 'react';
import { usePolling } from '../hooks/usePolling';
import { api } from '../api/client';
import {
  ResponsiveContainer, LineChart, Line, XAxis, YAxis, Tooltip, CartesianGrid,
} from 'recharts';

export default function Trading() {
  const { data: status, refresh } = usePolling(api.tradingStatus, 3000);
  const { data: portfolios } = usePolling(api.portfolios, 10000);

  const isRunning = status?.status === 'running';

  const handleStart = async () => {
    await api.tradingStart({ name: 'paper_trading', capital: 1000000, interval: 60 });
    refresh();
  };

  const handleStop = async () => {
    await api.tradingStop();
    refresh();
  };

  return (
    <div>
      <div className="grid grid-4">
        <div className="card">
          <h3>Executor Status</h3>
          <div className="stat-value">
            <span className={`badge badge-${isRunning ? 'success' : status?.status === 'killed' ? 'danger' : 'warning'}`}>
              {status?.status || 'idle'}
            </span>
          </div>
        </div>
        <div className="card">
          <h3>Trades Executed</h3>
          <div className="stat-value">{status?.trades_executed || 0}</div>
        </div>
        <div className="card">
          <h3>Cycle Count</h3>
          <div className="stat-value">{status?.cycle_count || 0}</div>
        </div>
        <div className="card">
          <h3>Broker</h3>
          <div className="stat-value">{status?.broker || 'None'}</div>
        </div>
      </div>

      <div className="card">
        <h3>Controls</h3>
        <div style={{display: 'flex', gap: '12px'}}>
          {!isRunning ? (
            <button className="btn btn-primary" onClick={handleStart}>Start Paper Trading</button>
          ) : (
            <button className="btn btn-danger" onClick={handleStop}>Stop Trading</button>
          )}
        </div>
      </div>

      <div className="card">
        <h3>Portfolios</h3>
        <table>
          <thead>
            <tr><th>Name</th><th>Initial Capital</th><th>Currency</th><th>Active</th></tr>
          </thead>
          <tbody>
            {(portfolios || []).map(p => (
              <tr key={p.id}>
                <td>{p.name}</td>
                <td>{p.initial_capital?.toLocaleString()}</td>
                <td>{p.currency}</td>
                <td><span className={`badge badge-${p.is_active ? 'success' : 'warning'}`}>{p.is_active ? 'Yes' : 'No'}</span></td>
              </tr>
            ))}
            {(!portfolios || portfolios.length === 0) && (
              <tr><td colSpan="4" style={{textAlign: 'center', color: 'var(--text-secondary)'}}>No portfolios — start trading to create one</td></tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
