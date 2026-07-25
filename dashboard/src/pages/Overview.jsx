import React, { useState, useMemo } from 'react';
import { usePolling } from '../hooks/usePolling';
import { api } from '../api/client';
import {
  ResponsiveContainer, AreaChart, Area, XAxis, YAxis, Tooltip, CartesianGrid,
  BarChart, Bar, Cell, ReferenceLine, Treemap, Legend,
} from 'recharts';

const COLORS = ['#0d6efd', '#198754', '#ffc107', '#dc3545', '#6f42c1', '#20c997', '#fd7e14'];
const RANGE_OPTIONS = ['1D', '1W', '1M', '3M', 'ALL'];

function ConfidenceGauge({ score }) {
  const pct = Math.max(0, Math.min(score, 100));
  const angle = (pct / 100) * 180;
  const rad = (a) => (a * Math.PI) / 180;
  const cx = 100, cy = 90, r = 70;
  const x1 = cx + r * Math.cos(rad(180));
  const y1 = cy - r * Math.sin(rad(180));
  const x2 = cx + r * Math.cos(rad(180 - angle));
  const y2 = cy - r * Math.sin(rad(180 - angle));
  const largeArc = angle > 180 ? 1 : 0;
  const color = pct >= 70 ? '#198754' : pct >= 40 ? '#ffc107' : '#dc3545';

  return (
    <svg viewBox="0 0 200 110" style={{width: '100%', maxWidth: '220px', display: 'block', margin: '0 auto'}}>
      <path d={`M ${cx - r} ${cy} A ${r} ${r} 0 0 1 ${cx + r} ${cy}`}
            fill="none" stroke="var(--border)" strokeWidth="12" strokeLinecap="round" />
      {pct > 0 && (
        <path d={`M ${x1} ${y1} A ${r} ${r} 0 ${largeArc} 1 ${x2} ${y2}`}
              fill="none" stroke={color} strokeWidth="12" strokeLinecap="round" />
      )}
      <text x={cx} y={cy - 10} textAnchor="middle" fill="var(--text)" fontSize="28" fontWeight="700">
        {Math.round(pct)}
      </text>
      <text x={cx} y={cy + 12} textAnchor="middle" fill="var(--text-secondary)" fontSize="11">
        Portfolio Health
      </text>
    </svg>
  );
}

function TreemapContent({ x, y, width, height, name, pnl }) {
  if (width < 40 || height < 30) return null;
  return (
    <g>
      <rect x={x} y={y} width={width} height={height} rx={4}
            fill={(pnl || 0) >= 0 ? '#198754' : '#dc3545'}
            fillOpacity={0.7} stroke="var(--card-bg)" strokeWidth={2} />
      <text x={x + width / 2} y={y + height / 2 - 6} textAnchor="middle" fill="#fff" fontSize={11} fontWeight={600}>
        {name && name.length > 12 ? name.slice(0, 12) + '..' : name}
      </text>
      <text x={x + width / 2} y={y + height / 2 + 10} textAnchor="middle" fill="#ffffffcc" fontSize={10}>
        {(pnl || 0) >= 0 ? '+' : ''}{(pnl || 0).toFixed(0)}
      </text>
    </g>
  );
}

export default function Overview() {
  const { data: health } = usePolling(api.health, 5000);
  const { data: strategies } = usePolling(api.strategies, 10000);
  const { data: riskHealth } = usePolling(api.riskHealth, 10000);
  const { data: trades } = usePolling(api.allTrades, 10000);
  const { data: positions } = usePolling(api.allPositions, 10000);
  const [dateRange, setDateRange] = useState('ALL');

  const tradeList = trades || [];
  const positionList = positions || [];
  const strategyList = strategies || [];

  const { equityCurve, winLossData, drawdownData, totalPnl, totalWinRate, overallSharpe, maxDrawdown } = useMemo(() => {
    if (tradeList.length === 0) return {
      equityCurve: [], winLossData: [], drawdownData: [],
      totalPnl: 0, totalWinRate: 0, overallSharpe: 0, maxDrawdown: 0,
    };

    const sorted = [...tradeList].sort((a, b) => (a.timestamp || a.created_at || '').localeCompare(b.timestamp || b.created_at || ''));

    let cumPnl = 0;
    let peak = 0;
    const curve = [];
    const dailyMap = {};
    const pnls = [];

    sorted.forEach(t => {
      const pnl = t.pnl || t.realized_pnl || 0;
      cumPnl += pnl;
      pnls.push(pnl);
      if (cumPnl > peak) peak = cumPnl;
      const dd = peak > 0 ? ((peak - cumPnl) / peak) * 100 : 0;
      const day = (t.timestamp || t.created_at || '').slice(0, 10);
      curve.push({ time: t.timestamp || t.created_at || '', cumPnl: Math.round(cumPnl), drawdown: -dd.toFixed(2) });

      if (day) {
        if (!dailyMap[day]) dailyMap[day] = { wins: 0, losses: 0 };
        if (pnl >= 0) dailyMap[day].wins++; else dailyMap[day].losses++;
      }
    });

    const winCount = pnls.filter(p => p >= 0).length;
    const wr = pnls.length > 0 ? (winCount / pnls.length) * 100 : 0;
    const mean = pnls.length > 0 ? pnls.reduce((a, b) => a + b, 0) / pnls.length : 0;
    const variance = pnls.length > 1 ? pnls.reduce((a, p) => a + (p - mean) ** 2, 0) / (pnls.length - 1) : 0;
    const stddev = Math.sqrt(variance);
    const sharpe = stddev > 0 ? (mean / stddev) * Math.sqrt(252) : 0;
    const maxDd = curve.length > 0 ? Math.max(...curve.map(c => Math.abs(parseFloat(c.drawdown)))) : 0;

    const wlData = Object.entries(dailyMap).map(([day, v]) => ({
      day, wins: v.wins, losses: -v.losses,
      winRate: v.wins + v.losses > 0 ? (v.wins / (v.wins + v.losses)) * 100 : 0,
    }));

    const ddData = curve.map(c => ({ time: c.time, drawdown: parseFloat(c.drawdown) }));

    let filteredCurve = curve;
    if (dateRange !== 'ALL' && curve.length > 0) {
      const now = new Date();
      let cutoff = new Date();
      if (dateRange === '1D') cutoff.setDate(now.getDate() - 1);
      else if (dateRange === '1W') cutoff.setDate(now.getDate() - 7);
      else if (dateRange === '1M') cutoff.setMonth(now.getMonth() - 1);
      else if (dateRange === '3M') cutoff.setMonth(now.getMonth() - 3);
      const cutStr = cutoff.toISOString();
      filteredCurve = curve.filter(c => c.time >= cutStr);
    }

    return {
      equityCurve: filteredCurve,
      winLossData: wlData.slice(-30),
      drawdownData: ddData,
      totalPnl: cumPnl,
      totalWinRate: wr,
      overallSharpe: sharpe,
      maxDrawdown: maxDd,
    };
  }, [tradeList, dateRange]);

  const activeStrategies = strategyList.filter(s => s.status === 'promoted' || s.status === 'paper_trading').length;

  const healthScore = useMemo(() => {
    let score = 50;
    if (health?.status === 'ok') score += 10;
    if (!health?.kill_switch?.is_active) score += 10;
    if (totalWinRate >= 60) score += 15;
    else if (totalWinRate >= 40) score += 5;
    if (overallSharpe >= 1) score += 10;
    if (maxDrawdown < 15) score += 5;
    else if (maxDrawdown > 30) score -= 10;
    return Math.max(0, Math.min(100, score));
  }, [health, totalWinRate, overallSharpe, maxDrawdown]);

  const treemapData = strategyList
    .filter(s => s.status === 'promoted' || s.status === 'paper_trading')
    .map(s => ({
      name: s.name,
      size: Math.max(Math.abs(s.net_profit_after_fees || s.net_profit || 1000), 100),
      pnl: s.net_profit_after_fees || s.net_profit || 0,
    }));

  return (
    <div>
      <div className="grid grid-6">
        <div className="card">
          <h3>Total P&L</h3>
          <div className="stat-value" style={{color: totalPnl >= 0 ? 'var(--success)' : 'var(--danger)'}}>
            {totalPnl >= 0 ? '+' : ''}{totalPnl.toFixed(0)}
          </div>
        </div>
        <div className="card">
          <h3>Win Rate</h3>
          <div className="stat-value" style={{color: totalWinRate >= 60 ? 'var(--success)' : totalWinRate >= 40 ? 'var(--warning)' : 'var(--danger)'}}>
            {totalWinRate.toFixed(1)}%
          </div>
        </div>
        <div className="card">
          <h3>Sharpe Ratio</h3>
          <div className="stat-value">{overallSharpe.toFixed(2)}</div>
        </div>
        <div className="card">
          <h3>Max Drawdown</h3>
          <div className="stat-value" style={{color: maxDrawdown > 15 ? 'var(--danger)' : 'var(--text)'}}>
            {maxDrawdown.toFixed(1)}%
          </div>
        </div>
        <div className="card">
          <h3>Active Strategies</h3>
          <div className="stat-value">{activeStrategies}</div>
        </div>
        <div className="card">
          <h3>Open Positions</h3>
          <div className="stat-value">{positionList.length}</div>
        </div>
      </div>

      <div className="grid grid-2">
        <div className="card">
          <h3>Portfolio Confidence</h3>
          <ConfidenceGauge score={healthScore} />
        </div>
        <div className="card">
          <h3>System Status</h3>
          <div style={{display: 'flex', flexDirection: 'column', gap: '8px'}}>
            <div style={{display: 'flex', justifyContent: 'space-between', alignItems: 'center'}}>
              <span>API Server</span>
              <span style={{width: '12px', height: '12px', borderRadius: '50%', background: health?.status === 'ok' ? '#198754' : '#dc3545', display: 'inline-block'}} />
            </div>
            <div style={{display: 'flex', justifyContent: 'space-between', alignItems: 'center'}}>
              <span>Kill Switch</span>
              <span style={{width: '12px', height: '12px', borderRadius: '50%', background: health?.kill_switch?.is_active ? '#dc3545' : '#198754', display: 'inline-block'}} />
            </div>
            <div style={{display: 'flex', justifyContent: 'space-between', alignItems: 'center'}}>
              <span>Risk Monitor</span>
              <span style={{width: '12px', height: '12px', borderRadius: '50%', background: riskHealth?.status === 'healthy' ? '#198754' : '#ffc107', display: 'inline-block'}} />
            </div>
          </div>
        </div>
      </div>

      <div className="card">
        <div style={{display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '12px'}}>
          <h3 style={{margin: 0}}>P&L Equity Curve</h3>
          <div style={{display: 'flex', gap: '4px'}}>
            {RANGE_OPTIONS.map(r => (
              <button key={r}
                      onClick={() => setDateRange(r)}
                      className="btn btn-sm"
                      style={{
                        background: dateRange === r ? 'var(--accent)' : 'var(--border)',
                        color: dateRange === r ? '#fff' : 'var(--text)',
                        padding: '4px 10px', fontSize: '11px',
                      }}>
                {r}
              </button>
            ))}
          </div>
        </div>
        {equityCurve.length > 0 ? (
          <ResponsiveContainer width="100%" height={300}>
            <AreaChart data={equityCurve}>
              <defs>
                <linearGradient id="pnlGrad" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="#198754" stopOpacity={0.4} />
                  <stop offset="95%" stopColor="#198754" stopOpacity={0} />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
              <XAxis dataKey="time" tick={{fill: 'var(--text-secondary)', fontSize: 10}} tickFormatter={v => v.slice(5, 10)} />
              <YAxis tick={{fill: 'var(--text-secondary)'}} />
              <Tooltip contentStyle={{background: 'var(--card-bg)', border: '1px solid var(--border)', color: 'var(--text)'}} />
              <Area type="monotone" dataKey="cumPnl" stroke="#198754" fill="url(#pnlGrad)" name="Cumulative P&L" />
            </AreaChart>
          </ResponsiveContainer>
        ) : (
          <div style={{textAlign: 'center', color: 'var(--text-secondary)', padding: '40px', fontSize: '13px'}}>
            No trade data yet. Execute trades to see the equity curve.
          </div>
        )}
      </div>

      {winLossData.length > 0 && (
        <div className="card">
          <h3>Daily Win/Loss Distribution</h3>
          <ResponsiveContainer width="100%" height={250}>
            <BarChart data={winLossData} stackOffset="sign">
              <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
              <XAxis dataKey="day" tick={{fill: 'var(--text-secondary)', fontSize: 10}} tickFormatter={v => v.slice(5)} />
              <YAxis tick={{fill: 'var(--text-secondary)'}} />
              <Tooltip contentStyle={{background: 'var(--card-bg)', border: '1px solid var(--border)', color: 'var(--text)'}} />
              <ReferenceLine y={0} stroke="var(--border)" />
              <Bar dataKey="wins" fill="#198754" name="Wins" stackId="stack" />
              <Bar dataKey="losses" fill="#dc3545" name="Losses" stackId="stack" />
            </BarChart>
          </ResponsiveContainer>
        </div>
      )}

      {drawdownData.length > 0 && (
        <div className="card">
          <h3>Drawdown</h3>
          <ResponsiveContainer width="100%" height={200}>
            <AreaChart data={drawdownData}>
              <defs>
                <linearGradient id="ddGrad" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="#dc3545" stopOpacity={0.4} />
                  <stop offset="95%" stopColor="#dc3545" stopOpacity={0} />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
              <XAxis dataKey="time" tick={{fill: 'var(--text-secondary)', fontSize: 10}} tickFormatter={v => v.slice(5, 10)} />
              <YAxis tick={{fill: 'var(--text-secondary)'}} domain={['dataMin', 0]} />
              <Tooltip contentStyle={{background: 'var(--card-bg)', border: '1px solid var(--border)', color: 'var(--text)'}} />
              <Area type="monotone" dataKey="drawdown" stroke="#dc3545" fill="url(#ddGrad)" name="Drawdown %" />
            </AreaChart>
          </ResponsiveContainer>
        </div>
      )}

      {treemapData.length > 0 && (
        <div className="card">
          <h3>Strategy Capital Allocation</h3>
          <ResponsiveContainer width="100%" height={250}>
            <Treemap data={treemapData} dataKey="size" nameKey="name"
                     content={<TreemapContent />} />
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
