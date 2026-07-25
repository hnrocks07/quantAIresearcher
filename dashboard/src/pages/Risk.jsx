import React, { useState, useEffect } from 'react';
import { usePolling } from '../hooks/usePolling';
import { api } from '../api/client';
import {
  ResponsiveContainer, BarChart, Bar, XAxis, YAxis, Tooltip, CartesianGrid, Cell,
  LineChart, Line, Legend, ReferenceLine,
} from 'recharts';

const COLORS = ['#0d6efd', '#198754', '#ffc107', '#dc3545', '#6f42c1', '#20c997', '#fd7e14'];
const VERDICT_COLORS = { keep: '#198754', adjust: '#ffc107', demote: '#dc3545' };

export default function Risk() {
  const { data: health } = usePolling(api.riskHealth, 10000);
  const { data: corr } = usePolling(api.correlation, 15000);
  const { data: reviewLog } = usePolling(api.riskReviewLog, 15000);
  const { data: dailyLoss } = usePolling(api.dailyLoss, 15000);
  const { data: strategies } = usePolling(api.strategies, 10000);
  const [regime, setRegime] = useState('bearish');
  const [stressData, setStressData] = useState(null);
  const [allStressData, setAllStressData] = useState({});
  const [selectedReview, setSelectedReview] = useState(null);

  const runStress = async () => {
    const result = await api.stressTest(regime);
    setStressData(result);
    setAllStressData(prev => ({...prev, [regime]: result}));
  };

  const runAllStress = async () => {
    const results = {};
    for (const r of ['bullish', 'bearish', 'crash']) {
      try {
        const result = await api.stressTest(r);
        results[r] = result;
      } catch (e) { /* skip */ }
    }
    setAllStressData(results);
    setStressData(results[regime] || null);
  };

  const handleReview = async (strategyId) => {
    await api.riskReview(strategyId, {});
  };

  const handleRotate = async () => {
    await api.riskRotate();
  };

  const stressChartData = (stressData?.strategies || []).map(s => ({
    name: s.name.length > 20 ? s.name.slice(0, 20) + '..' : s.name,
    original: s.original_pnl,
    stressed: s.stressed_pnl,
    survives: s.survives,
  }));

  const groupedStressData = [];
  const stressRegimes = Object.keys(allStressData);
  if (stressRegimes.length > 1) {
    const allNames = new Set();
    stressRegimes.forEach(r => {
      (allStressData[r]?.strategies || []).forEach(s => allNames.add(s.name));
    });
    allNames.forEach(name => {
      const entry = { name: name.length > 15 ? name.slice(0, 15) + '..' : name };
      stressRegimes.forEach(r => {
        const s = (allStressData[r]?.strategies || []).find(x => x.name === name);
        entry[r] = s ? s.stressed_pnl : 0;
      });
      groupedStressData.push(entry);
    });
  }

  const flaggedStrategies = (health?.strategy_summary || []).filter(s =>
    s.flags || s.flagged || (s.win_rate != null && s.win_rate < 0.4) || (s.drawdown != null && s.drawdown > 0.2)
  );

  const corrMatrix = corr?.matrix || corr?.correlation_matrix || {};
  const corrNames = Object.keys(corrMatrix);

  const pipelineCounts = {};
  const statuses = ['discovered', 'backtesting', 'scored', 'shortlisted', 'paper_trading', 'promoted'];
  statuses.forEach(s => { pipelineCounts[s] = 0; });
  let demotedCount = 0;
  (strategies || []).forEach(s => {
    if (pipelineCounts[s.status] !== undefined) pipelineCounts[s.status]++;
    if (s.status === 'demoted') demotedCount++;
  });

  const reviews = reviewLog || [];

  return (
    <div>
      <div className="grid grid-4">
        <div className="card">
          <h3>Portfolio Health</h3>
          <div className="stat-value">
            <span className={'badge badge-' + (health?.status === 'healthy' ? 'success' : 'warning')}>
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

      {flaggedStrategies.length > 0 && (
        <div className="card">
          <h3>Flagged Strategies</h3>
          <div className="grid grid-3">
            {flaggedStrategies.map((s, i) => (
              <div key={i} style={{
                background: 'var(--bg)',
                borderRadius: '8px',
                padding: '16px',
                border: '2px solid var(--danger)',
              }}>
                <div style={{fontWeight: 600, marginBottom: '8px'}}>{s.name}</div>
                <div style={{fontSize: '12px', display: 'flex', flexDirection: 'column', gap: '4px'}}>
                  <div>Win Rate: <span style={{color: (s.win_rate || 0) < 0.4 ? 'var(--danger)' : 'var(--text)'}}>
                    {s.win_rate != null ? (s.win_rate * 100).toFixed(1) + '%' : '-'}
                  </span></div>
                  <div>Drawdown: <span style={{color: (s.drawdown || 0) > 0.2 ? 'var(--danger)' : 'var(--text)'}}>
                    {s.drawdown != null ? (s.drawdown * 100).toFixed(1) + '%' : '-'}
                  </span></div>
                  <div>Sharpe: {s.sharpe?.toFixed(2) || '-'}</div>
                  {s.flags && <div style={{color: 'var(--danger)', fontWeight: 500}}>{Array.isArray(s.flags) ? s.flags.join(', ') : s.flags}</div>}
                  {s.recommendation && <div style={{color: 'var(--warning)'}}>{s.recommendation}</div>}
                </div>
                <button className="btn btn-sm btn-danger" onClick={() => handleReview(s.strategy_id || s.id)}
                        style={{marginTop: '8px', fontSize: '11px'}}>
                  Request Review
                </button>
              </div>
            ))}
          </div>
        </div>
      )}

      {reviews.length > 0 && (
        <div className="card">
          <h3>Review Recommendations</h3>
          <div style={{display: 'flex', flexDirection: 'column', gap: '12px'}}>
            {reviews.slice(0, 10).map((r, i) => (
              <div key={i} style={{
                display: 'flex', gap: '16px', background: 'var(--bg)',
                borderRadius: '8px', padding: '16px', border: '1px solid var(--border)',
                cursor: 'pointer',
              }} onClick={() => setSelectedReview(selectedReview === i ? null : i)}>
                <div style={{flex: 1}}>
                  <div style={{fontWeight: 600, marginBottom: '4px'}}>{r.strategy_name || r.strategy || 'Strategy'}</div>
                  <div style={{fontSize: '12px', color: 'var(--text-secondary)', display: 'flex', gap: '12px', flexWrap: 'wrap'}}>
                    <span>Win Rate: {r.win_rate != null ? (r.win_rate * 100).toFixed(1) + '%' : '-'}</span>
                    <span>Sharpe: {r.sharpe?.toFixed(2) || '-'}</span>
                    <span>Drawdown: {r.drawdown != null ? (r.drawdown * 100).toFixed(1) + '%' : '-'}</span>
                    <span>Time: {r.timestamp || ''}</span>
                  </div>
                  {selectedReview === i && r.reasoning && (
                    <div style={{marginTop: '8px', fontSize: '13px', color: 'var(--text-secondary)', lineHeight: '1.5'}}>
                      {r.reasoning}
                    </div>
                  )}
                </div>
                <div style={{flexShrink: 0, display: 'flex', alignItems: 'center'}}>
                  <span className="badge" style={{
                    background: (VERDICT_COLORS[r.verdict] || '#8b949e') + '22',
                    color: VERDICT_COLORS[r.verdict] || '#8b949e',
                    fontWeight: 700, fontSize: '13px', padding: '4px 12px',
                  }}>
                    {(r.verdict || 'pending').toUpperCase()}
                  </span>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {selectedReview !== null && reviews[selectedReview]?.before_equity && reviews[selectedReview]?.after_equity && (
        <div className="card">
          <h3>Before/After Equity Overlay</h3>
          <ResponsiveContainer width="100%" height={250}>
            <LineChart>
              <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
              <XAxis dataKey="idx" tick={{fill: 'var(--text-secondary)', fontSize: 10}} />
              <YAxis tick={{fill: 'var(--text-secondary)'}} />
              <Tooltip contentStyle={{background: 'var(--card-bg)', border: '1px solid var(--border)', color: 'var(--text)'}} />
              <Legend />
              <Line data={reviews[selectedReview].before_equity.map((v, idx) => ({idx, v}))}
                    type="monotone" dataKey="v" stroke="#8b949e" strokeDasharray="5 5" name="Before" dot={false} />
              <Line data={reviews[selectedReview].after_equity.map((v, idx) => ({idx, v}))}
                    type="monotone" dataKey="v" stroke="#0d6efd" name="After" dot={false} strokeWidth={2} />
            </LineChart>
          </ResponsiveContainer>
        </div>
      )}

      <div className="card">
        <h3>Promotion / Demotion Flow</h3>
        <div style={{display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '4px', flexWrap: 'wrap', padding: '16px 0'}}>
          {statuses.map((s, i) => (
            <React.Fragment key={s}>
              <div style={{
                background: 'var(--bg)',
                border: '2px solid ' + (s === 'promoted' ? '#198754' : 'var(--border)'),
                borderRadius: '8px',
                padding: '12px 16px',
                textAlign: 'center',
                minWidth: '90px',
              }}>
                <div style={{fontSize: '20px', fontWeight: 700}}>{pipelineCounts[s] || 0}</div>
                <div style={{fontSize: '10px', textTransform: 'uppercase', color: 'var(--text-secondary)', marginTop: '2px'}}>{s.replace('_', ' ')}</div>
              </div>
              {i < statuses.length - 1 && (
                <span style={{fontSize: '18px', color: 'var(--text-secondary)'}}>&rarr;</span>
              )}
            </React.Fragment>
          ))}
          <span style={{fontSize: '18px', color: 'var(--text-secondary)', marginLeft: '12px'}}>&darr;</span>
          <div style={{
            background: '#dc354522',
            border: '2px solid #dc3545',
            borderRadius: '8px',
            padding: '12px 16px',
            textAlign: 'center',
            minWidth: '90px',
          }}>
            <div style={{fontSize: '20px', fontWeight: 700, color: '#dc3545'}}>{demotedCount}</div>
            <div style={{fontSize: '10px', textTransform: 'uppercase', color: '#dc3545', marginTop: '2px'}}>demoted</div>
          </div>
        </div>
        <div style={{textAlign: 'center', marginTop: '8px'}}>
          <button className="btn btn-success btn-sm" onClick={handleRotate}>Run Rotation</button>
        </div>
      </div>

      {corrNames.length > 0 && (
        <div className="card">
          <h3>Correlation Matrix</h3>
          <div style={{overflowX: 'auto'}}>
            <table style={{fontSize: '12px'}}>
              <thead>
                <tr>
                  <th></th>
                  {corrNames.map(n => (
                    <th key={n} style={{writingMode: 'vertical-rl', textOrientation: 'mixed', maxWidth: '30px'}}>
                      {n.length > 12 ? n.slice(0, 12) + '..' : n}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {corrNames.map(row => (
                  <tr key={row}>
                    <td style={{fontWeight: 500, whiteSpace: 'nowrap'}}>
                      {row.length > 15 ? row.slice(0, 15) + '..' : row}
                    </td>
                    {corrNames.map(col => {
                      const val = corrMatrix[row]?.[col] ?? corrMatrix[row]?.[col.toLowerCase()] ?? 0;
                      const absVal = Math.abs(val);
                      let bg = 'transparent';
                      if (row !== col) {
                        if (absVal > 0.7) bg = '#dc354544';
                        else if (absVal > 0.4) bg = '#ffc10744';
                        else bg = '#19875422';
                      }
                      return (
                        <td key={col} style={{
                          background: bg,
                          textAlign: 'center',
                          fontWeight: absVal > 0.7 ? 700 : 400,
                          color: absVal > 0.7 ? 'var(--danger)' : 'var(--text)',
                          minWidth: '50px',
                        }}>
                          {row === col ? '1.00' : val.toFixed(2)}
                        </td>
                      );
                    })}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <div style={{fontSize: '11px', color: 'var(--text-secondary)', marginTop: '8px'}}>
            Green = low correlation (&lt;0.4) | Yellow = medium (0.4-0.7) | Red = high (&gt;0.7)
          </div>
        </div>
      )}

      {corr?.highly_correlated_pairs?.length > 0 && (
        <div className="card" style={{borderColor: 'var(--warning)'}}>
          <h3>Highly Correlated Pairs (&gt;70%)</h3>
          <table>
            <thead><tr><th>Strategy A</th><th>Strategy B</th><th>Correlation</th></tr></thead>
            <tbody>
              {corr.highly_correlated_pairs.map((p, i) => (
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
        <div style={{display: 'flex', gap: '12px', marginBottom: '16px', alignItems: 'center', flexWrap: 'wrap'}}>
          <select value={regime} onChange={e => setRegime(e.target.value)}
                  style={{padding: '8px', borderRadius: '6px', border: '1px solid var(--border)', background: 'var(--card-bg)', color: 'var(--text)'}}>
            <option value="bearish">Bearish (-30%)</option>
            <option value="sideways">Sideways (0%)</option>
            <option value="bullish">Bullish (+30%)</option>
            <option value="crash">Crash (-50%)</option>
          </select>
          <button className="btn btn-primary" onClick={runStress}>Run Stress Test</button>
          <button className="btn btn-sm" onClick={runAllStress}
                  style={{background: 'var(--border)', color: 'var(--text)'}}>
            Run All Regimes
          </button>
        </div>

        {stressData && (
          <div>
            <div className="grid grid-3" style={{marginBottom: '16px'}}>
              <div><strong>Survivors:</strong> {stressData.survivors}/{stressData.total_strategies}</div>
              <div><strong>Stressed P&L:</strong> <span style={{color: stressData.total_stressed_pnl >= 0 ? 'var(--success)' : 'var(--danger)'}}>{stressData.total_stressed_pnl?.toFixed(0) || 0}</span></div>
              <div><strong>Portfolio Survives:</strong> {stressData.portfolio_survives ? 'Yes' : 'No'}</div>
            </div>
            {stressChartData.length > 0 && (
              <ResponsiveContainer width="100%" height={300}>
                <BarChart data={stressChartData}>
                  <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
                  <XAxis dataKey="name" angle={-45} textAnchor="end" height={80} fontSize={11} tick={{fill: 'var(--text)'}} />
                  <YAxis tick={{fill: 'var(--text-secondary)'}} />
                  <Tooltip contentStyle={{background: 'var(--card-bg)', border: '1px solid var(--border)', color: 'var(--text)'}} />
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

        {groupedStressData.length > 0 && (
          <div style={{marginTop: '16px'}}>
            <h3 style={{fontSize: '13px', color: 'var(--text-secondary)', textTransform: 'uppercase', marginBottom: '12px'}}>
              Grouped Regime Comparison
            </h3>
            <ResponsiveContainer width="100%" height={300}>
              <BarChart data={groupedStressData}>
                <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
                <XAxis dataKey="name" angle={-45} textAnchor="end" height={80} fontSize={11} tick={{fill: 'var(--text)'}} />
                <YAxis tick={{fill: 'var(--text-secondary)'}} />
                <Tooltip contentStyle={{background: 'var(--card-bg)', border: '1px solid var(--border)', color: 'var(--text)'}} />
                <Legend />
                {stressRegimes.map((r, i) => (
                  <Bar key={r} dataKey={r} fill={COLORS[i % COLORS.length]} name={r} />
                ))}
              </BarChart>
            </ResponsiveContainer>
          </div>
        )}
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
                <td><span className="badge badge-info">{s.status}</span></td>
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
    </div>
  );
}
