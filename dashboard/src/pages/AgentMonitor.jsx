import React, { useState, useMemo } from 'react';
import { usePolling } from '../hooks/usePolling';
import { api } from '../api/client';

const AGENT_COLORS = {
  signal_agent: '#0d6efd',
  decision_agent: '#198754',
  review_agent: '#6f42c1',
  risk_agent: '#ffc107',
  execution_agent: '#fd7e14',
};

export default function AgentMonitor() {
  const { data: activityFeed } = usePolling(api.agentsActivityFeed, 5000);
  const [filterAgent, setFilterAgent] = useState('');
  const [filterAction, setFilterAction] = useState('');
  const [expandedIdx, setExpandedIdx] = useState(null);

  const feed = activityFeed || [];

  const agentStats = useMemo(() => {
    const stats = {};
    feed.forEach(entry => {
      const name = entry.agent_name || 'unknown';
      if (!stats[name]) {
        stats[name] = { total: 0, lastAction: '', lastTime: '', successes: 0, errors: 0, actions: {} };
      }
      stats[name].total++;
      if (!stats[name].lastTime || (entry.timestamp || '') > stats[name].lastTime) {
        stats[name].lastTime = entry.timestamp || '';
        stats[name].lastAction = entry.action || '';
      }
      if (entry.status === 'error' || entry.action === 'error') {
        stats[name].errors++;
      } else {
        stats[name].successes++;
      }
      const action = entry.action || 'other';
      stats[name].actions[action] = (stats[name].actions[action] || 0) + 1;
    });
    return stats;
  }, [feed]);

  const agentNames = Object.keys(agentStats);
  const allActions = [...new Set(feed.map(e => e.action).filter(Boolean))];

  const filteredFeed = useMemo(() => {
    let result = feed;
    if (filterAgent) {
      result = result.filter(e => e.agent_name === filterAgent);
    }
    if (filterAction) {
      result = result.filter(e => e.action === filterAction);
    }
    return result;
  }, [feed, filterAgent, filterAction]);

  return (
    <div>
      <div className="grid grid-3">
        {agentNames.length === 0 ? (
          <div className="card" style={{gridColumn: '1 / -1'}}>
            <div style={{textAlign: 'center', color: 'var(--text-secondary)', padding: '20px', fontSize: '13px'}}>
              No agent activity yet. Start research or trading to see agents.
            </div>
          </div>
        ) : (
          agentNames.map(name => {
            const s = agentStats[name];
            const successRate = s.total > 0 ? ((s.successes / s.total) * 100).toFixed(0) : '0';
            const color = AGENT_COLORS[name] || '#8b949e';
            return (
              <div key={name} className="card" style={{borderLeft: '3px solid ' + color}}>
                <div style={{display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px'}}>
                  <span style={{fontWeight: 700, fontSize: '15px'}}>{name}</span>
                  <span className="badge badge-success" style={{fontSize: '10px'}}>
                    {s.lastTime ? 'active' : 'idle'}
                  </span>
                </div>
                <div style={{display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '8px', fontSize: '13px'}}>
                  <div>
                    <div style={{color: 'var(--text-secondary)', fontSize: '11px'}}>Total Actions</div>
                    <div style={{fontWeight: 600, fontSize: '20px'}}>{s.total}</div>
                  </div>
                  <div>
                    <div style={{color: 'var(--text-secondary)', fontSize: '11px'}}>Success Rate</div>
                    <div style={{fontWeight: 600, fontSize: '20px', color: parseInt(successRate) >= 80 ? 'var(--success)' : parseInt(successRate) >= 50 ? 'var(--warning)' : 'var(--danger)'}}>
                      {successRate}%
                    </div>
                  </div>
                </div>
                <div style={{marginTop: '8px', fontSize: '11px', color: 'var(--text-secondary)'}}>
                  Last: {s.lastAction} at {s.lastTime || 'N/A'}
                </div>
                {Object.keys(s.actions).length > 0 && (
                  <div style={{marginTop: '8px', display: 'flex', gap: '4px', flexWrap: 'wrap'}}>
                    {Object.entries(s.actions).slice(0, 6).map(([action, count]) => (
                      <span key={action} style={{
                        fontSize: '10px', padding: '2px 6px', borderRadius: '4px',
                        background: 'var(--bg)', border: '1px solid var(--border)',
                      }}>
                        {action}: {count}
                      </span>
                    ))}
                  </div>
                )}
              </div>
            );
          })
        )}
      </div>

      <div className="card">
        <h3>Activity Feed</h3>
        <div style={{display: 'flex', gap: '12px', marginBottom: '12px', flexWrap: 'wrap'}}>
          <select value={filterAgent} onChange={e => setFilterAgent(e.target.value)}
                  style={{padding: '6px 12px', borderRadius: '6px', border: '1px solid var(--border)', background: 'var(--card-bg)', color: 'var(--text)', fontSize: '13px'}}>
            <option value="">All Agents</option>
            {agentNames.map(n => <option key={n} value={n}>{n}</option>)}
          </select>
          <select value={filterAction} onChange={e => setFilterAction(e.target.value)}
                  style={{padding: '6px 12px', borderRadius: '6px', border: '1px solid var(--border)', background: 'var(--card-bg)', color: 'var(--text)', fontSize: '13px'}}>
            <option value="">All Actions</option>
            {allActions.map(a => <option key={a} value={a}>{a}</option>)}
          </select>
          <span style={{fontSize: '12px', color: 'var(--text-secondary)', alignSelf: 'center'}}>
            {filteredFeed.length} entries
          </span>
        </div>
        <div style={{maxHeight: '600px', overflowY: 'auto', display: 'flex', flexDirection: 'column', gap: '8px'}}>
          {filteredFeed.length === 0 && (
            <div style={{textAlign: 'center', color: 'var(--text-secondary)', padding: '30px', fontSize: '13px'}}>
              No activity entries
            </div>
          )}
          {filteredFeed.slice(0, 100).map((entry, i) => {
            const agentColor = AGENT_COLORS[entry.agent_name] || '#8b949e';
            const isExpanded = expandedIdx === i;
            return (
              <div key={i} style={{
                background: 'var(--bg)',
                borderRadius: '8px',
                padding: '12px 16px',
                border: '1px solid var(--border)',
                cursor: 'pointer',
                transition: 'border-color 0.2s',
              }} onClick={() => setExpandedIdx(isExpanded ? null : i)}>
                <div style={{display: 'flex', gap: '10px', alignItems: 'center', flexWrap: 'wrap'}}>
                  <span className="badge" style={{
                    background: agentColor + '22',
                    color: agentColor,
                    fontSize: '11px',
                    fontWeight: 600,
                  }}>
                    {entry.agent_name || 'unknown'}
                  </span>
                  <span style={{fontWeight: 600, fontSize: '13px'}}>{entry.action || ''}</span>
                  <span style={{flex: 1}} />
                  <span style={{fontSize: '11px', color: 'var(--text-secondary)'}}>{entry.timestamp || ''}</span>
                  <span style={{fontSize: '11px', color: 'var(--text-secondary)', cursor: 'pointer'}}>
                    {isExpanded ? '▲' : '▼'}
                  </span>
                </div>
                {entry.reasoning && (
                  <div style={{marginTop: '6px', fontSize: '12px', color: 'var(--text-secondary)'}}>
                    {isExpanded ? entry.reasoning : (entry.reasoning.length > 100 ? entry.reasoning.slice(0, 100) + '...' : entry.reasoning)}
                  </div>
                )}
                {isExpanded && entry.details && (
                  <div style={{
                    marginTop: '8px', fontSize: '12px', color: 'var(--text)',
                    background: 'var(--card-bg)', padding: '10px', borderRadius: '6px',
                    border: '1px solid var(--border)', whiteSpace: 'pre-wrap', lineHeight: '1.5',
                  }}>
                    {typeof entry.details === 'object' ? JSON.stringify(entry.details, null, 2) : entry.details}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}
