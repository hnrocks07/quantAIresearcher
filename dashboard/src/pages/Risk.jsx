import React, { useState, useEffect } from 'react';
import { usePolling } from '../hooks/usePolling';
import { api } from '../api/client';
import {
  ResponsiveContainer, BarChart, Bar, XAxis, YAxis, Tooltip, CartesianGrid, Cell,
  ScatterChart, Scatter, ZAxis,
} from 'recharts';

const COLORS = ['#0d6efd', '#198754', '#ffc107', '#dc3545', '#6f42c1', '#20c997', '#fd7e14'];

export default function Risk() {
  const { data: health } = usePolling(api.riskHealth, 10000);
  const { data: corr } = usePolling(api.correlation, 15000);
  const [regime, setRegime] = useState('bearish');
  const [stressData, setStressData] = useState(null);

  const runStress = async () => {
    const result = await api.stressTest(regime);
    setStressData(result);
  };

  const handlePromoteDemote = async () => {
    await api.promoteDemote();
  };

  const stressChartData = (stressData?.strategies || []).map(s => ({
    name: s.name.length > 20 ? s.name.slice(0, 20) + '...' : s.name,
    original: s.original_pnl,
    stressed: s.stressed_pnl,
    survives: s.survives,
  }));

  const corrPairs = corr?.highly_correlated_pairs || [];

  return (
    <div>
      <div className="grid grid-4">
        <div className="card">
          <h3>Portfolio Health</h3>
          <div className="stat-value">
            <span className={`badge badge-${health?.status === 'healthy' ? 'success' : 'warning'}`}>
              {health?.status || 'Unknown'}
            </span>
          </div>
        </div>
        <div className="card">
          <h3>Active Strategies</h3>
          <div className="stat-value">{health?.strategies || 0}</div>
        </div>
        <div className="card">
          <h3>Diversified</h3>
          <div className="stat-value">{health?.diversified ? 'Yes' : 'No'}</div>
        </div>
        <div className="card">
          <h3>Max Drawdown</h3>
          <div className="stat-value" style={{color: (health?.max_drawdown || 0) > 0.15 ? 'var(--danger)' : 'var(--text)'}}>
            {((health?.max_drawdown || 0) * 100).toFixed(1)}%
          </div>
        </div>
      </div>

      <div className="card">
        <h3>Strategy Health Summary</h3>
        <table>
          <thead>
            <tr><th>Name</th><th>Status</th><th>Win Rate</th><th>Sharpe</th><th>Drawdown</th><th>Net Profit</th></tr>
          </thead>
          <tbody>
            {(health?.strategy_summary || []).map((s, i) => (
              <tr key={i}>
                <td>{s.name}</td>
                <td><span className={`badge badge-info`}>{s.status}</span></td>
                <td>{s.win_rate != null ? (s.win_rate * 100).toFixed(1) + '%' : '-'}</td>
                <td>{s.sharpe?.toFixed(2) || '-'}</td>
                <td>{s.drawdown != null ? (s.drawdown * 100).toFixed(1) + '%' : '-'}</td>
                <td style={{color: (s.net_profit || 0) >= 0 ? 'var(--success)' : 'var(--danger)'}}>
                  {s.net_profit?.toFixed(0) || '-'}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {corrPairs.length > 0 && (
        <div className="card" style={{borderColor: 'var(--warning)'}}>
          <h3>Highly Correlated Strategy Pairs (>{'>'}70%)</h3>
          <table>
            <thead><tr><th>Strategy A</th><th>Strategy B</th><th>Correlation</th></tr></thead>
            <tbody>
              {corrPairs.map((p, i) => (
                <tr key={i}>
                  <td>{p.pair[0]}</td>
                  <td>{p.pair[1]}</td>
                  <td style={{color: 'var(--danger)'}}>{(p.correlation * 100).toFixed(1)}%</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <div className="card">
        <h3>Stress Test</h3>
        <div style={{display: 'flex', gap: '12px', marginBottom: '16px', alignItems: 'center'}}>
          <select value={regime} onChange={e => setRegime(e.target.value)}
                  style={{padding: '8px', borderRadius: '6px', border: '1px solid var(--border)', background: 'var(--card-bg)', color: 'var(--text)'}}>
            <option value="bearish">Bearish (-30%)</option>
            <option value="sideways">Sideways (0%)</option>
            <option value="bullish">Bullish (+30%)</option>
          </select>
          <button className="btn btn-primary" onClick={runStress}>Run Stress Test</button>
          <button className="btn btn-success" onClick={handlePromoteDemote}>Auto Promote/Demote</button>
        </div>

        {stressData && (
          <div>
            <div className="grid grid-3" style={{marginBottom: '16px'}}>
              <div><strong>Survivors:</strong> {stressData.survivors}/{stressData.total_strategies}</div>
              <div><strong>Stressed P&L:</strong> <span style={{color: stressData.total_stressed_pnl >= 0 ? 'var(--success)' : 'var(--danger)'}}>{stressData.total_stressed_pnl.toFixed(0)}</span></div>
              <div><strong>Portfolio Survives:</strong> {stressData.portfolio_survives ? 'Yes' : 'No'}</div>
            </div>
            {stressChartData.length > 0 && (
              <ResponsiveContainer width="100%" height={300}>
                <BarChart data={stressChartData}>
                  <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
                  <XAxis dataKey="name" angle={-45} textAnchor="end" height={80} fontSize={11} />
                  <YAxis />
                  <Tooltip />
                  <Bar dataKey="original" fill="#0d6efd" name="Original P&L" />
                  <Bar dataKey="stressed" name="Stressed P&L">
                    {stressChartData.map((entry, i) => (
                      <Cell key={i} fill={entry.survives ? '#198754' : '#dc3545'} />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
