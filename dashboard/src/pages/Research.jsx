import React, { useState, useEffect, useRef, useCallback } from 'react';
import { usePolling } from '../hooks/usePolling';
import { api } from '../api/client';
import {
  ResponsiveContainer, RadarChart, Radar, PolarGrid, PolarAngleAxis, PolarRadiusAxis,
  BarChart, Bar, XAxis, YAxis, Tooltip, CartesianGrid, ReferenceLine,
} from 'recharts';

const KANBAN_COLUMNS = ['discovered', 'backtesting', 'scored', 'shortlisted'];
const KANBAN_COLORS = {
  discovered: '#6f42c1',
  backtesting: '#0d6efd',
  scored: '#ffc107',
  shortlisted: '#198754',
};

export default function Research() {
  const { data: status, refresh } = usePolling(api.researchStatus, 3000);
  const { data: strategies } = usePolling(api.strategies, 8000);
  const { data: activityLog } = usePolling(api.researchActivityLog, 5000);
  const { data: errors } = usePolling(api.researchErrors, 15000);
  const [sourceMode, setSourceMode] = useState('both');
  const [selectedStrategy, setSelectedStrategy] = useState(null);
  const feedRef = useRef(null);

  useEffect(() => {
    if (feedRef.current) {
      feedRef.current.scrollTop = feedRef.current.scrollHeight;
    }
  }, [activityLog]);

  const handleStart = async () => {
    await api.researchStart({ source_mode: sourceMode });
    refresh();
  };

  const handleStop = async () => {
    await api.researchStop();
    refresh();
  };

  const isRunning = status?.status === 'running';

  const kanbanData = {};
  KANBAN_COLUMNS.forEach(col => { kanbanData[col] = []; });
  (strategies || []).forEach(s => {
    if (kanbanData[s.status]) {
      kanbanData[s.status].push(s);
    }
  });

  const radarData = selectedStrategy ? [
    { metric: 'Win Rate', value: (selectedStrategy.win_rate || 0) * 100, threshold: 80 },
    { metric: 'Sharpe', value: Math.min(Math.max((selectedStrategy.sharpe_ratio || 0) * 33, 0), 100), threshold: 80 },
    { metric: 'Profit Factor', value: Math.min((selectedStrategy.profit_factor || 0) * 25, 100), threshold: 80 },
    { metric: 'Low Drawdown', value: (1 - (selectedStrategy.max_drawdown || 0)) * 100, threshold: 80 },
    { metric: 'Trade Count', value: Math.min(((selectedStrategy.trade_count || 0) / 100) * 100, 100), threshold: 80 },
  ] : [];

  const scoredStrategies = (strategies || []).filter(s => s.win_rate != null);
  const barData = scoredStrategies.slice(0, 15).map(s => ({
    name: s.name.length > 18 ? s.name.slice(0, 18) + '..' : s.name,
    win_rate: (s.win_rate || 0) * 100,
    sharpe: Math.max(s.sharpe_ratio || 0, 0) * 20,
  }));

  return (
    <div>
      <div className="grid grid-4">
        <div className="card">
          <h3>Status</h3>
          <div className="stat-value">
            <span className={'badge badge-' + (isRunning ? 'info' : status?.status === 'completed' ? 'success' : 'warning')}>
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
          <select value={sourceMode} onChange={e => setSourceMode(e.target.value)}
                  style={{padding: '8px', borderRadius: '6px', border: '1px solid var(--border)', background: 'var(--card-bg)', color: 'var(--text)'}}>
            <option value="tradingview">TradingView</option>
            <option value="builtin">Built-in</option>
            <option value="both">Both</option>
          </select>
          {!isRunning ? (
            <button className="btn btn-primary" onClick={handleStart}>Start Research</button>
          ) : (
            <button className="btn btn-danger" onClick={handleStop}>Stop Research</button>
          )}
          <span style={{fontSize: '12px', color: 'var(--text-secondary)'}}>
            Elapsed: {Math.round((status?.elapsed_seconds || 0) / 60)}m | Errors: {status?.errors_count || 0}
          </span>
        </div>
      </div>

      <div className="card">
        <h3>Strategy Pipeline</h3>
        <div style={{display: 'flex', gap: '12px', overflowX: 'auto', minHeight: '300px'}}>
          {KANBAN_COLUMNS.map(col => (
            <div key={col} style={{
              flex: '1 0 200px',
              background: 'var(--bg)',
              borderRadius: '8px',
              padding: '12px',
              border: '1px solid var(--border)',
            }}>
              <div style={{
                display: 'flex', justifyContent: 'space-between', alignItems: 'center',
                marginBottom: '12px', paddingBottom: '8px', borderBottom: '2px solid ' + KANBAN_COLORS[col],
              }}>
                <span style={{fontWeight: 600, fontSize: '13px', textTransform: 'uppercase'}}>{col}</span>
                <span className="badge badge-info" style={{background: KANBAN_COLORS[col], color: '#fff'}}>
                  {kanbanData[col].length}
                </span>
              </div>
              <div style={{display: 'flex', flexDirection: 'column', gap: '8px', maxHeight: '400px', overflowY: 'auto'}}>
                {kanbanData[col].map(s => (
                  <div key={s.id}
                       onClick={() => setSelectedStrategy(s)}
                       style={{
                         background: 'var(--card-bg)',
                         borderRadius: '6px',
                         padding: '10px',
                         border: selectedStrategy?.id === s.id ? '2px solid var(--accent)' : '1px solid var(--border)',
                         cursor: 'pointer',
                         fontSize: '13px',
                         transition: 'border-color 0.2s',
                       }}>
                    <div style={{fontWeight: 600, marginBottom: '4px'}}>{s.name}</div>
                    <div style={{display: 'flex', gap: '8px', fontSize: '11px', color: 'var(--text-secondary)'}}>
                      {s.win_rate != null && <span>WR: {(s.win_rate * 100).toFixed(0)}%</span>}
                      {s.sharpe_ratio != null && <span>SR: {s.sharpe_ratio.toFixed(2)}</span>}
                    </div>
                  </div>
                ))}
                {kanbanData[col].length === 0 && (
                  <div style={{textAlign: 'center', color: 'var(--text-secondary)', fontSize: '12px', padding: '20px 0'}}>
                    No strategies
                  </div>
                )}
              </div>
            </div>
          ))}
        </div>
      </div>

      {selectedStrategy && (
        <div className="card">
          <h3>Scorecard: {selectedStrategy.name}</h3>
          <ResponsiveContainer width="100%" height={350}>
            <RadarChart data={radarData}>
              <PolarGrid stroke="var(--border)" />
              <PolarAngleAxis dataKey="metric" tick={{fill: 'var(--text)', fontSize: 12}} />
              <PolarRadiusAxis angle={30} domain={[0, 100]} tick={{fill: 'var(--text-secondary)', fontSize: 10}} />
              <Radar name="Score" dataKey="value" stroke="#0d6efd" fill="#0d6efd" fillOpacity={0.3} />
              <Radar name="80% Threshold" dataKey="threshold" stroke="#dc3545" fill="none" strokeDasharray="5 5" />
              <Tooltip contentStyle={{background: 'var(--card-bg)', border: '1px solid var(--border)', color: 'var(--text)'}} />
            </RadarChart>
          </ResponsiveContainer>
          <div style={{textAlign: 'center', fontSize: '12px', color: 'var(--text-secondary)'}}>
            Dashed red line = 80% promotion threshold
          </div>
        </div>
      )}

      {barData.length > 0 && (
        <div className="card">
          <h3>Strategy Win Rates vs Promotion Threshold</h3>
          <ResponsiveContainer width="100%" height={300}>
            <BarChart data={barData} margin={{left: 0, right: 20}}>
              <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
              <XAxis dataKey="name" angle={-45} textAnchor="end" height={80} fontSize={11} tick={{fill: 'var(--text)'}} />
              <YAxis domain={[0, 100]} tick={{fill: 'var(--text-secondary)'}} />
              <Tooltip contentStyle={{background: 'var(--card-bg)', border: '1px solid var(--border)', color: 'var(--text)'}} />
              <ReferenceLine y={80} stroke="#dc3545" strokeDasharray="5 5" label={{value: '80% Threshold', fill: '#dc3545', fontSize: 11}} />
              <Bar dataKey="win_rate" fill="#198754" name="Win Rate %" />
            </BarChart>
          </ResponsiveContainer>
        </div>
      )}

      <div className="card">
        <h3>Research Activity Feed</h3>
        <div ref={feedRef} style={{
          maxHeight: '300px',
          overflowY: 'auto',
          background: 'var(--bg)',
          borderRadius: '6px',
          padding: '8px',
          border: '1px solid var(--border)',
        }}>
          {(activityLog || []).length === 0 && (
            <div style={{textAlign: 'center', color: 'var(--text-secondary)', padding: '20px', fontSize: '13px'}}>
              No activity yet. Start research to see the feed.
            </div>
          )}
          {(activityLog || []).map((entry, i) => (
            <div key={i} style={{
              padding: '8px 12px',
              borderBottom: '1px solid var(--border)',
              fontSize: '13px',
              display: 'flex',
              gap: '12px',
              alignItems: 'flex-start',
            }}>
              <span style={{color: 'var(--text-secondary)', fontSize: '11px', whiteSpace: 'nowrap', minWidth: '140px'}}>
                {entry.timestamp || ''}
              </span>
              <span className={'badge badge-' + (entry.action === 'shortlisted' ? 'success' : entry.action === 'error' ? 'danger' : 'info')}
                    style={{fontSize: '10px', flexShrink: 0}}>
                {entry.action || 'info'}
              </span>
              <span style={{fontWeight: 500}}>{entry.strategy || ''}</span>
              <span style={{color: 'var(--text-secondary)', flex: 1}}>{entry.reasoning || entry.message || ''}</span>
            </div>
          ))}
        </div>
      </div>

      {errors && errors.length > 0 && (
        <div className="card" style={{borderColor: 'var(--danger)'}}>
          <h3>Research Errors</h3>
          <table>
            <thead><tr><th>Time</th><th>Error</th></tr></thead>
            <tbody>
              {errors.slice(0, 20).map((e, i) => (
                <tr key={i}>
                  <td style={{fontSize: '12px'}}>{e.timestamp || ''}</td>
                  <td style={{color: 'var(--danger)', fontSize: '12px'}}>{e.error || e.message || ''}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
