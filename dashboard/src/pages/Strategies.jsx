import React, { useState } from 'react';
import { usePolling } from '../hooks/usePolling';
import { api } from '../api/client';
import {
  ResponsiveContainer, BarChart, Bar, XAxis, YAxis, Tooltip, CartesianGrid,
  RadarChart, Radar, PolarGrid, PolarAngleAxis, PolarRadiusAxis,
} from 'recharts';

export default function Strategies() {
  const [filter, setFilter] = useState('');
  const { data: strategies } = usePolling(() => api.strategies(filter), 10000);
  const { data: rankings } = usePolling(api.scoringRank, 15000);

  const barData = (rankings || []).slice(0, 15).map(r => ({
    name: r.name.length > 20 ? r.name.slice(0, 20) + '...' : r.name,
    score: r.composite_score,
    winRate: r.win_rate,
    sharpe: Math.max(r.sharpe_ratio, 0),
  }));

  const radarData = (rankings || []).slice(0, 5).map(r => ({
    name: r.name.length > 15 ? r.name.slice(0, 15) : r.name,
    'Win Rate': r.win_rate * 100,
    'Sharpe': Math.min(Math.max(r.sharpe_ratio * 33, 0), 100),
    'Profit Factor': Math.min(r.profit_factor * 25, 100),
    'Low Drawdown': (1 - r.max_drawdown) * 100,
    'Net Profit': Math.min(Math.max(r.net_profit / 1000, 0), 100),
  }));

  const statuses = ['', 'discovered', 'backtesting', 'scored', 'shortlisted', 'paper_trading', 'promoted', 'demoted', 'retired'];

  return (
    <div>
      <div style={{marginBottom: '16px'}}>
        <select value={filter} onChange={e => setFilter(e.target.value)}
                style={{padding: '8px', borderRadius: '6px', border: '1px solid var(--border)', background: 'var(--card-bg)', color: 'var(--text)'}}>
          {statuses.map(s => (
            <option key={s} value={s}>{s || 'All Statuses'}</option>
          ))}
        </select>
      </div>

      {barData.length > 0 && (
        <div className="card">
          <h3>Top Strategies by Composite Score</h3>
          <ResponsiveContainer width="100%" height={300}>
            <BarChart data={barData} margin={{left: 0, right: 20}}>
              <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
              <XAxis dataKey="name" angle={-45} textAnchor="end" height={80} fontSize={11} />
              <YAxis />
              <Tooltip />
              <Bar dataKey="score" fill="#0d6efd" name="Score" />
              <Bar dataKey="winRate" fill="#198754" name="Win Rate" />
            </BarChart>
          </ResponsiveContainer>
        </div>
      )}

      {radarData.length > 0 && (
        <div className="card">
          <h3>Strategy Comparison (Top 5)</h3>
          <ResponsiveContainer width="100%" height={400}>
            <RadarChart data={[
              { metric: 'Win Rate', ...Object.fromEntries(radarData.map(r => [r.name, r['Win Rate']])) },
              { metric: 'Sharpe', ...Object.fromEntries(radarData.map(r => [r.name, r['Sharpe']])) },
              { metric: 'Profit Factor', ...Object.fromEntries(radarData.map(r => [r.name, r['Profit Factor']])) },
              { metric: 'Low Drawdown', ...Object.fromEntries(radarData.map(r => [r.name, r['Low Drawdown']])) },
              { metric: 'Net Profit', ...Object.fromEntries(radarData.map(r => [r.name, r['Net Profit']])) },
            ]}>
              <PolarGrid />
              <PolarAngleAxis dataKey="metric" />
              <PolarRadiusAxis angle={30} domain={[0, 100]} />
              {radarData.map((r, i) => (
                <Radar key={r.name} name={r.name} dataKey={r.name}
                       stroke={['#0d6efd','#198754','#ffc107','#dc3545','#6f42c1'][i]}
                       fill={['#0d6efd','#198754','#ffc107','#dc3545','#6f42c1'][i]}
                       fillOpacity={0.1} />
              ))}
            </RadarChart>
          </ResponsiveContainer>
        </div>
      )}

      <div className="card">
        <h3>Strategy List</h3>
        <table>
          <thead>
            <tr>
              <th>Name</th><th>Status</th><th>Win Rate</th><th>Sharpe</th>
              <th>Drawdown</th><th>Net Profit</th><th>Source</th>
            </tr>
          </thead>
          <tbody>
            {(strategies || []).map(s => (
              <tr key={s.id}>
                <td>{s.name}</td>
                <td><span className={`badge badge-${s.status === 'promoted' ? 'success' : s.status === 'demoted' ? 'danger' : 'info'}`}>{s.status}</span></td>
                <td>{s.win_rate != null ? (s.win_rate * 100).toFixed(1) + '%' : '-'}</td>
                <td>{s.sharpe_ratio?.toFixed(2) || '-'}</td>
                <td>{s.max_drawdown != null ? (s.max_drawdown * 100).toFixed(1) + '%' : '-'}</td>
                <td style={{color: (s.net_profit_after_fees || 0) >= 0 ? 'var(--success)' : 'var(--danger)'}}>
                  {s.net_profit_after_fees != null ? s.net_profit_after_fees.toFixed(0) : '-'}
                </td>
                <td>{s.source}</td>
              </tr>
            ))}
            {(!strategies || strategies.length === 0) && (
              <tr><td colSpan="7" style={{textAlign: 'center', color: 'var(--text-secondary)'}}>No strategies yet — run research first</td></tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
