import React, { useState } from 'react';
import { usePolling } from '../hooks/usePolling';
import { api } from '../api/client';
import {
  ResponsiveContainer, LineChart, Line, XAxis, YAxis, Tooltip, CartesianGrid,
} from 'recharts';

const ACTION_COLORS = {
  buy: '#198754',
  sell: '#dc3545',
  hold: '#ffc107',
  signal: '#0d6efd',
  evaluate: '#6f42c1',
  promote: '#20c997',
  demote: '#fd7e14',
};

const STATUS_COLORS = {
  pending: '#ffc107',
  filled: '#198754',
  cancelled: '#dc3545',
  rejected: '#dc3545',
  partial: '#fd7e14',
};

export default function Trading() {
  const { data: status, refresh } = usePolling(api.tradingStatus, 3000);
  const { data: portfolios } = usePolling(api.portfolios, 10000);
  const { data: trades } = usePolling(api.allTrades, 8000);
  const { data: positions } = usePolling(api.allPositions, 8000);
  const { data: activityFeed } = usePolling(api.agentsActivityFeed, 5000);
  const { data: strategies } = usePolling(() => api.strategies('paper_trading'), 15000);
  const [promotingId, setPromotingId] = useState(null);

  const isRunning = status?.status === 'running';

  const handleStart = async () => {
    await api.tradingStart({ name: 'paper_trading', capital: 1000000, interval: 60 });
    refresh();
  };

  const handleStop = async () => {
    await api.tradingStop();
    refresh();
  };

  const handlePromotionEval = async (strategyId) => {
    setPromotingId(strategyId);
    try {
      await api.tradingPromotionEvaluate(strategyId);
    } finally {
      setPromotingId(null);
    }
  };

  const agentTypes = {};
  (activityFeed || []).forEach(entry => {
    if (!agentTypes[entry.agent_name]) {
      agentTypes[entry.agent_name] = { total: 0, lastAction: null };
    }
    agentTypes[entry.agent_name].total++;
    if (!agentTypes[entry.agent_name].lastAction || entry.timestamp > agentTypes[entry.agent_name].lastAction) {
      agentTypes[entry.agent_name].lastAction = entry.timestamp;
    }
  });

  return (
    <div>
      <div className="grid grid-4">
        <div className="card">
          <h3>Executor Status</h3>
          <div className="stat-value">
            <span className={'badge badge-' + (isRunning ? 'success' : status?.status === 'killed' ? 'danger' : 'warning')}>
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
          <div className="stat-value">{status?.broker || 'Paper'}</div>
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
        <h3>Bot Status</h3>
        <div className="grid grid-3">
          {Object.entries(agentTypes).length === 0 ? (
            <div style={{color: 'var(--text-secondary)', fontSize: '13px', gridColumn: '1 / -1', textAlign: 'center', padding: '20px'}}>
              No agent activity yet
            </div>
          ) : (
            Object.entries(agentTypes).map(([name, info]) => (
              <div key={name} style={{
                background: 'var(--bg)',
                borderRadius: '8px',
                padding: '16px',
                border: '1px solid var(--border)',
              }}>
                <div style={{display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px'}}>
                  <span style={{fontWeight: 600, fontSize: '14px'}}>{name}</span>
                  <span className="badge badge-success" style={{fontSize: '10px'}}>active</span>
                </div>
                <div style={{fontSize: '12px', color: 'var(--text-secondary)'}}>
                  <div>Total actions: {info.total}</div>
                  <div>Last: {info.lastAction || 'N/A'}</div>
                </div>
              </div>
            ))
          )}
        </div>
      </div>

      <div className="card">
        <h3>Decision Trail Timeline</h3>
        <div style={{maxHeight: '400px', overflowY: 'auto', position: 'relative', paddingLeft: '20px'}}>
          <div style={{
            position: 'absolute', left: '8px', top: 0, bottom: 0, width: '2px',
            background: 'var(--border)',
          }} />
          {(activityFeed || []).length === 0 && (
            <div style={{textAlign: 'center', color: 'var(--text-secondary)', padding: '20px', fontSize: '13px'}}>
              No decisions yet
            </div>
          )}
          {(activityFeed || []).slice(0, 50).map((entry, i) => {
            const actionColor = ACTION_COLORS[entry.action] || '#8b949e';
            return (
              <div key={i} style={{
                position: 'relative',
                paddingLeft: '20px',
                paddingBottom: '16px',
                borderLeft: 'none',
              }}>
                <div style={{
                  position: 'absolute', left: '-6px', top: '4px',
                  width: '12px', height: '12px', borderRadius: '50%',
                  background: actionColor, border: '2px solid var(--card-bg)',
                }} />
                <div style={{display: 'flex', gap: '8px', alignItems: 'center', flexWrap: 'wrap'}}>
                  <span className="badge" style={{
                    background: actionColor + '22',
                    color: actionColor,
                    fontSize: '10px',
                  }}>{entry.agent_name}</span>
                  <span style={{fontWeight: 600, fontSize: '13px'}}>{entry.action}</span>
                  <span style={{fontSize: '11px', color: 'var(--text-secondary)'}}>{entry.timestamp || ''}</span>
                </div>
                {entry.reasoning && (
                  <div style={{fontSize: '12px', color: 'var(--text-secondary)', marginTop: '4px'}}>
                    {entry.reasoning.length > 120 ? entry.reasoning.slice(0, 120) + '...' : entry.reasoning}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      </div>

      <div className="card">
        <h3>Order Book (Recent Trades)</h3>
        <table>
          <thead>
            <tr>
              <th>Time</th><th>Symbol</th><th>Side</th><th>Qty</th>
              <th>Price</th><th>Status</th><th>Strategy</th>
            </tr>
          </thead>
          <tbody>
            {(trades || []).slice(0, 30).map((t, i) => (
              <tr key={i}>
                <td style={{fontSize: '12px'}}>{t.timestamp || t.created_at || ''}</td>
                <td style={{fontWeight: 600}}>{t.symbol}</td>
                <td style={{color: t.side === 'buy' ? 'var(--success)' : 'var(--danger)', fontWeight: 600}}>
                  {(t.side || '').toUpperCase()}
                </td>
                <td>{t.quantity || t.qty}</td>
                <td>{t.price?.toLocaleString()}</td>
                <td>
                  <span className="badge" style={{
                    background: (STATUS_COLORS[t.status] || '#8b949e') + '22',
                    color: STATUS_COLORS[t.status] || '#8b949e',
                    fontWeight: 600,
                  }}>
                    {t.status || 'unknown'}
                  </span>
                </td>
                <td style={{fontSize: '12px', color: 'var(--text-secondary)'}}>{t.strategy || t.strategy_name || ''}</td>
              </tr>
            ))}
            {(!trades || trades.length === 0) && (
              <tr><td colSpan="7" style={{textAlign: 'center', color: 'var(--text-secondary)'}}>No trades yet</td></tr>
            )}
          </tbody>
        </table>
      </div>

      <div className="card">
        <h3>Open Positions</h3>
        <table>
          <thead>
            <tr>
              <th>Symbol</th><th>Side</th><th>Qty</th><th>Entry Price</th>
              <th>Current Price</th><th>Unrealized P&L</th><th>Strategy</th><th>Trend</th>
            </tr>
          </thead>
          <tbody>
            {(positions || []).map((p, i) => {
              const pnl = p.unrealized_pnl || ((p.current_price || 0) - (p.entry_price || 0)) * (p.quantity || p.qty || 0) * (p.side === 'short' ? -1 : 1);
              const history = p.price_history || [];
              return (
                <tr key={i}>
                  <td style={{fontWeight: 600}}>{p.symbol}</td>
                  <td style={{color: p.side === 'long' || p.side === 'buy' ? 'var(--success)' : 'var(--danger)'}}>
                    {(p.side || '').toUpperCase()}
                  </td>
                  <td>{p.quantity || p.qty}</td>
                  <td>{p.entry_price?.toLocaleString()}</td>
                  <td>{p.current_price?.toLocaleString()}</td>
                  <td style={{color: pnl >= 0 ? 'var(--success)' : 'var(--danger)', fontWeight: 600}}>
                    {pnl >= 0 ? '+' : ''}{pnl.toFixed(2)}
                  </td>
                  <td style={{fontSize: '12px'}}>{p.strategy || p.strategy_name || ''}</td>
                  <td>
                    {history.length > 2 ? (
                      <ResponsiveContainer width={50} height={20}>
                        <LineChart data={history.map((v, idx) => ({v, idx}))}>
                          <Line type="monotone" dataKey="v" stroke={pnl >= 0 ? '#198754' : '#dc3545'} dot={false} strokeWidth={1.5} />
                        </LineChart>
                      </ResponsiveContainer>
                    ) : (
                      <span style={{fontSize: '11px', color: 'var(--text-secondary)'}}>--</span>
                    )}
                  </td>
                </tr>
              );
            })}
            {(!positions || positions.length === 0) && (
              <tr><td colSpan="8" style={{textAlign: 'center', color: 'var(--text-secondary)'}}>No open positions</td></tr>
            )}
          </tbody>
        </table>
      </div>

      <div className="card">
        <h3>Promotion Status (Paper Trading Strategies)</h3>
        {(strategies || []).length === 0 ? (
          <div style={{textAlign: 'center', color: 'var(--text-secondary)', padding: '20px', fontSize: '13px'}}>
            No strategies in paper trading
          </div>
        ) : (
          <div style={{display: 'flex', flexDirection: 'column', gap: '12px'}}>
            {(strategies || []).map(s => {
              const wrPct = Math.min(((s.win_rate || 0) * 100 / 80) * 100, 100);
              const tcPct = Math.min(((s.trade_count || 0) / 30) * 100, 100);
              const daysPct = Math.min(((s.days_active || 0) / 14) * 100, 100);
              return (
                <div key={s.id} style={{
                  background: 'var(--bg)', borderRadius: '8px', padding: '16px',
                  border: '1px solid var(--border)',
                }}>
                  <div style={{display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '12px'}}>
                    <span style={{fontWeight: 600}}>{s.name}</span>
                    <button className="btn btn-sm btn-primary"
                            onClick={() => handlePromotionEval(s.id)}
                            disabled={promotingId === s.id}
                            style={{fontSize: '11px'}}>
                      {promotingId === s.id ? 'Evaluating...' : 'Evaluate Promotion'}
                    </button>
                  </div>
                  <div style={{display: 'flex', flexDirection: 'column', gap: '8px'}}>
                    {[
                      { label: 'Win Rate', pct: wrPct, value: ((s.win_rate || 0) * 100).toFixed(1) + '% / 80%' },
                      { label: 'Trade Count', pct: tcPct, value: (s.trade_count || 0) + ' / 30' },
                      { label: 'Days Active', pct: daysPct, value: (s.days_active || 0) + ' / 14' },
                    ].map(bar => (
                      <div key={bar.label}>
                        <div style={{display: 'flex', justifyContent: 'space-between', fontSize: '12px', marginBottom: '4px'}}>
                          <span>{bar.label}</span>
                          <span style={{color: 'var(--text-secondary)'}}>{bar.value}</span>
                        </div>
                        <div style={{background: 'var(--border)', borderRadius: '4px', height: '8px', overflow: 'hidden'}}>
                          <div style={{
                            width: bar.pct + '%', height: '100%',
                            background: bar.pct >= 100 ? '#198754' : '#0d6efd',
                            borderRadius: '4px',
                            transition: 'width 0.5s ease',
                          }} />
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}
