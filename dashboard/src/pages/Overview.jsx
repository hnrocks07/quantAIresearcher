import React from 'react';
import { usePolling } from '../hooks/usePolling';
import { api } from '../api/client';
import {
  ResponsiveContainer, AreaChart, Area, XAxis, YAxis, Tooltip,
  PieChart, Pie, Cell, Legend,
} from 'recharts';

const COLORS = ['#0d6efd', '#198754', '#ffc107', '#dc3545', '#6f42c1', '#20c997'];

export default function Overview() {
  const { data: health } = usePolling(api.health, 5000);
  const { data: strategies } = usePolling(api.strategies, 10000);
  const { data: riskHealth } = usePolling(api.riskHealth, 10000);
  const { data: ingest } = usePolling(api.ingestStatus, 5000);
  const { data: research } = usePolling(api.researchStatus, 5000);
  const { data: trading } = usePolling(api.tradingStatus, 5000);

  const statusCounts = {};
  if (strategies) {
    strategies.forEach(s => {
      statusCounts[s.status] = (statusCounts[s.status] || 0) + 1;
    });
  }
  const pieData = Object.entries(statusCounts).map(([name, value]) => ({ name, value }));

  return (
    <div>
      <div className="grid grid-4">
        <div className="card">
          <h3>System</h3>
          <div className="stat-value">{health?.status === 'ok' ? 'Online' : 'Offline'}</div>
          <div className="stat-label">v{health?.version}</div>
        </div>
        <div className="card">
          <h3>Kill Switch</h3>
          <div className="stat-value">
            {health?.kill_switch?.is_active ? (
              <span style={{color: 'var(--danger)'}}>ACTIVE</span>
            ) : (
              <span style={{color: 'var(--success)'}}>Safe</span>
            )}
          </div>
          <div className="stat-label">
            {health?.kill_switch?.safe_to_trade ? 'Trading allowed' : 'Trading blocked'}
          </div>
        </div>
        <div className="card">
          <h3>Strategies</h3>
          <div className="stat-value">{strategies?.length || 0}</div>
          <div className="stat-label">Total discovered</div>
        </div>
        <div className="card">
          <h3>Risk Status</h3>
          <div className="stat-value">
            <span className={`badge badge-${riskHealth?.status === 'healthy' ? 'success' : 'warning'}`}>
              {riskHealth?.status || 'Unknown'}
            </span>
          </div>
          <div className="stat-label">{riskHealth?.strategies || 0} active strategies</div>
        </div>
      </div>

      <div className="grid grid-3">
        <div className="card">
          <h3>Data Ingestion</h3>
          <div className="stat-value">{ingest?.status || 'idle'}</div>
          <div className="stat-label">
            {ingest?.processed || 0}/{ingest?.total_instruments || 0} instruments
            ({ingest?.rows_inserted || 0} rows)
          </div>
        </div>
        <div className="card">
          <h3>Research Engine</h3>
          <div className="stat-value">{research?.status || 'idle'}</div>
          <div className="stat-label">
            {research?.strategies_tested || 0} tested, {research?.strategies_shortlisted || 0} shortlisted
          </div>
        </div>
        <div className="card">
          <h3>Trading Executor</h3>
          <div className="stat-value">{trading?.status || 'idle'}</div>
          <div className="stat-label">
            {trading?.trades_executed || 0} trades, cycle #{trading?.cycle_count || 0}
          </div>
        </div>
      </div>

      {pieData.length > 0 && (
        <div className="card">
          <h3>Strategy Distribution</h3>
          <ResponsiveContainer width="100%" height={300}>
            <PieChart>
              <Pie data={pieData} dataKey="value" nameKey="name" cx="50%" cy="50%"
                   outerRadius={100} label={({name, value}) => `${name}: ${value}`}>
                {pieData.map((_, i) => (
                  <Cell key={i} fill={COLORS[i % COLORS.length]} />
                ))}
              </Pie>
              <Tooltip />
              <Legend />
            </PieChart>
          </ResponsiveContainer>
        </div>
      )}

      {riskHealth?.warnings?.length > 0 && (
        <div className="card" style={{borderColor: 'var(--warning)'}}>
          <h3>Warnings</h3>
          <ul style={{paddingLeft: '20px'}}>
            {riskHealth.warnings.map((w, i) => (
              <li key={i} style={{color: 'var(--warning)', marginBottom: '4px'}}>{w}</li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
