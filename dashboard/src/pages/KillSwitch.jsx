import React, { useState, useMemo } from 'react';
import { usePolling } from '../hooks/usePolling';
import { api } from '../api/client';

const NSE_HOLIDAYS_2026 = [
  '2026-01-26', '2026-03-14', '2026-03-31', '2026-04-10', '2026-04-14',
  '2026-04-18', '2026-05-01', '2026-06-26', '2026-07-17', '2026-08-15',
  '2026-08-27', '2026-10-02', '2026-10-21', '2026-10-22', '2026-11-05',
  '2026-11-26', '2026-12-25',
];

const HOLIDAY_NAMES = {
  '2026-01-26': 'Republic Day', '2026-03-14': 'Holi', '2026-03-31': 'Id-ul-Fitr',
  '2026-04-10': 'Good Friday', '2026-04-14': 'Dr. Ambedkar Jayanti', '2026-04-18': 'Ram Navami',
  '2026-05-01': 'May Day', '2026-06-26': 'Bakrid', '2026-07-17': 'Muharram',
  '2026-08-15': 'Independence Day', '2026-08-27': 'Janmashtami', '2026-10-02': 'Gandhi Jayanti',
  '2026-10-21': 'Dussehra', '2026-10-22': 'Dussehra', '2026-11-05': 'Diwali',
  '2026-11-26': 'Guru Nanak Jayanti', '2026-12-25': 'Christmas',
};

function MarketCalendar() {
  const [viewMonth, setViewMonth] = useState(() => {
    const d = new Date();
    return { year: d.getFullYear(), month: d.getMonth() };
  });

  const today = new Date().toISOString().slice(0, 10);
  const daysInMonth = new Date(viewMonth.year, viewMonth.month + 1, 0).getDate();
  const firstDay = new Date(viewMonth.year, viewMonth.month, 1).getDay();
  const monthName = new Date(viewMonth.year, viewMonth.month).toLocaleString('default', { month: 'long', year: 'numeric' });

  const cells = [];
  for (let i = 0; i < firstDay; i++) cells.push(null);
  for (let d = 1; d <= daysInMonth; d++) cells.push(d);

  const prevMonth = () => {
    setViewMonth(prev => {
      const m = prev.month - 1;
      return m < 0 ? { year: prev.year - 1, month: 11 } : { year: prev.year, month: m };
    });
  };
  const nextMonth = () => {
    setViewMonth(prev => {
      const m = prev.month + 1;
      return m > 11 ? { year: prev.year + 1, month: 0 } : { year: prev.year, month: m };
    });
  };

  return (
    <div>
      <div style={{display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '12px'}}>
        <button className="btn btn-sm" onClick={prevMonth} style={{background: 'var(--border)', color: 'var(--text)'}}>&larr;</button>
        <span style={{fontWeight: 600}}>{monthName}</span>
        <button className="btn btn-sm" onClick={nextMonth} style={{background: 'var(--border)', color: 'var(--text)'}}>&rarr;</button>
      </div>
      <div style={{display: 'grid', gridTemplateColumns: 'repeat(7, 1fr)', gap: '2px', textAlign: 'center', fontSize: '12px'}}>
        {['Sun','Mon','Tue','Wed','Thu','Fri','Sat'].map(d => (
          <div key={d} style={{padding: '4px', fontWeight: 600, color: 'var(--text-secondary)'}}>{d}</div>
        ))}
        {cells.map((day, i) => {
          if (!day) return <div key={'e' + i} />;
          const dateStr = `${viewMonth.year}-${String(viewMonth.month + 1).padStart(2, '0')}-${String(day).padStart(2, '0')}`;
          const isHoliday = NSE_HOLIDAYS_2026.includes(dateStr);
          const isToday = dateStr === today;
          const dayOfWeek = new Date(viewMonth.year, viewMonth.month, day).getDay();
          const isWeekend = dayOfWeek === 0 || dayOfWeek === 6;
          const isNonTrading = isHoliday || isWeekend;

          return (
            <div key={i} title={isHoliday ? HOLIDAY_NAMES[dateStr] || 'NSE Holiday' : isWeekend ? 'Weekend' : 'Trading Day'}
                 style={{
                   padding: '6px 2px',
                   borderRadius: '4px',
                   background: isToday ? 'var(--accent)' : isHoliday ? '#dc354533' : isWeekend ? 'var(--border)' : 'transparent',
                   color: isToday ? '#fff' : isHoliday ? '#dc3545' : isWeekend ? 'var(--text-secondary)' : 'var(--text)',
                   fontWeight: isToday ? 700 : 400,
                   cursor: 'default',
                 }}>
              {day}
            </div>
          );
        })}
      </div>
      <div style={{display: 'flex', gap: '12px', marginTop: '8px', fontSize: '11px', color: 'var(--text-secondary)'}}>
        <span><span style={{display: 'inline-block', width: '10px', height: '10px', borderRadius: '2px', background: 'var(--accent)', marginRight: '4px'}} />Today</span>
        <span><span style={{display: 'inline-block', width: '10px', height: '10px', borderRadius: '2px', background: '#dc354533', marginRight: '4px'}} />Holiday</span>
        <span><span style={{display: 'inline-block', width: '10px', height: '10px', borderRadius: '2px', background: 'var(--border)', marginRight: '4px'}} />Weekend</span>
      </div>
    </div>
  );
}

export default function KillSwitch() {
  const { data: status, refresh } = usePolling(api.killSwitchStatus, 2000);
  const { data: events } = usePolling(() => api.events(200), 5000);
  const { data: health } = usePolling(api.health, 5000);
  const { data: researchStatus } = usePolling(api.researchStatus, 10000);
  const { data: tradingStatus } = usePolling(api.tradingStatus, 10000);
  const { data: ingestStatus } = usePolling(api.ingestStatus, 10000);
  const [reason, setReason] = useState('manual emergency');
  const [eventFilter, setEventFilter] = useState('');
  const [dateFrom, setDateFrom] = useState('');
  const [dateTo, setDateTo] = useState('');

  const handleTrigger = async () => {
    await api.killSwitchTrigger(reason);
    refresh();
  };

  const handleReset = async () => {
    await api.killSwitchReset();
    refresh();
  };

  const handleHeartbeat = async () => {
    await api.killSwitchHeartbeat();
    refresh();
  };

  const isActive = status?.is_active;

  const systemHealth = [
    { name: 'API Server', status: health?.status === 'ok' ? 'green' : 'red' },
    { name: 'Database', status: health?.database === 'ok' || health?.status === 'ok' ? 'green' : 'red' },
    { name: 'Kill Switch', status: isActive ? 'red' : 'green' },
    { name: 'Research Engine', status: researchStatus?.status === 'running' ? 'green' : researchStatus?.status === 'error' ? 'red' : 'yellow' },
    { name: 'Trading Executor', status: tradingStatus?.status === 'running' ? 'green' : tradingStatus?.status === 'killed' ? 'red' : 'yellow' },
    { name: 'Broker Connection', status: tradingStatus?.broker ? 'green' : 'yellow' },
  ];

  const filteredEvents = useMemo(() => {
    let evts = events || [];
    if (eventFilter) {
      evts = evts.filter(e => (e.event_type || '').toLowerCase().includes(eventFilter.toLowerCase()));
    }
    if (dateFrom) {
      evts = evts.filter(e => (e.timestamp || '') >= dateFrom);
    }
    if (dateTo) {
      evts = evts.filter(e => (e.timestamp || '') <= dateTo + 'T23:59:59');
    }
    return evts;
  }, [events, eventFilter, dateFrom, dateTo]);

  const exportCSV = () => {
    const header = 'Timestamp,Event Type,Source,Details\n';
    const rows = filteredEvents.map(e =>
      `"${e.timestamp || ''}","${e.event_type || ''}","${e.source || ''}","${(e.details || e.message || '').replace(/"/g, '""')}"`
    ).join('\n');
    const blob = new Blob([header + rows], { type: 'text/csv' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = 'audit_trail_' + new Date().toISOString().slice(0, 10) + '.csv';
    a.click();
    URL.revokeObjectURL(url);
  };

  const todayStr = new Date().toISOString().slice(0, 10);
  const isHolidayToday = NSE_HOLIDAYS_2026.includes(todayStr);
  const dayOfWeek = new Date().getDay();
  const isTradingDay = !isHolidayToday && dayOfWeek !== 0 && dayOfWeek !== 6;

  return (
    <div>
      <div className="card">
        <h3>System Health</h3>
        <div style={{display: 'flex', gap: '24px', flexWrap: 'wrap', padding: '8px 0'}}>
          {systemHealth.map(s => (
            <div key={s.name} style={{display: 'flex', alignItems: 'center', gap: '8px'}}>
              <span style={{
                width: '14px', height: '14px', borderRadius: '50%', display: 'inline-block',
                background: s.status === 'green' ? '#198754' : s.status === 'red' ? '#dc3545' : '#ffc107',
                boxShadow: '0 0 6px ' + (s.status === 'green' ? '#19875466' : s.status === 'red' ? '#dc354566' : '#ffc10766'),
              }} />
              <span style={{fontSize: '13px'}}>{s.name}</span>
            </div>
          ))}
        </div>
        <div style={{fontSize: '12px', color: 'var(--text-secondary)', marginTop: '4px'}}>
          Market: {isTradingDay ? (
            <span style={{color: 'var(--success)', fontWeight: 600}}>Trading Day</span>
          ) : (
            <span style={{color: 'var(--danger)', fontWeight: 600}}>
              Non-Trading {isHolidayToday ? '(' + (HOLIDAY_NAMES[todayStr] || 'Holiday') + ')' : '(Weekend)'}
            </span>
          )}
        </div>
      </div>

      <div className="grid grid-3">
        <div className="card" style={{borderColor: isActive ? 'var(--danger)' : 'var(--success)', borderWidth: '2px'}}>
          <h3>Kill Switch</h3>
          <div className="stat-value" style={{fontSize: '36px', color: isActive ? 'var(--danger)' : 'var(--success)'}}>
            {isActive ? 'ACTIVE' : 'SAFE'}
          </div>
          <div className="stat-label">
            {status?.safe_to_trade ? 'Trading allowed' : 'ALL TRADING HALTED'}
          </div>
        </div>
        <div className="card">
          <h3>Triggered By</h3>
          <div className="stat-value" style={{fontSize: '18px'}}>{status?.triggered_by || 'None'}</div>
          <div className="stat-label">{status?.reason || ''}</div>
        </div>
        <div className="card">
          <h3>Last Heartbeat</h3>
          <div className="stat-value" style={{fontSize: '18px'}}>
            {status?.heartbeat_age != null ? status.heartbeat_age.toFixed(0) + 's ago' : 'Never'}
          </div>
          <div className="stat-label">Timeout: {status?.heartbeat_timeout || 15}s</div>
        </div>
      </div>

      <div className="card">
        <h3>Controls</h3>
        <div style={{display: 'flex', gap: '12px', alignItems: 'center', flexWrap: 'wrap'}}>
          <input
            type="text" value={reason} onChange={e => setReason(e.target.value)}
            placeholder="Reason..."
            style={{padding: '8px 12px', borderRadius: '6px', border: '1px solid var(--border)', background: 'var(--card-bg)', color: 'var(--text)', width: '250px'}}
          />
          <button className="btn btn-danger" onClick={handleTrigger}
                  style={{fontSize: '16px', padding: '12px 24px'}}>
            TRIGGER KILL SWITCH
          </button>
          <button className="btn btn-success" onClick={handleReset}>Reset</button>
          <button className="btn btn-primary btn-sm" onClick={handleHeartbeat}>Send Heartbeat</button>
        </div>
      </div>

      <div className="grid grid-2">
        <div className="card">
          <h3>NSE Market Calendar 2026</h3>
          <MarketCalendar />
        </div>
        <div className="card">
          <h3>Notifications Config</h3>
          <div style={{display: 'flex', flexDirection: 'column', gap: '12px'}}>
            <div>
              <label style={{fontSize: '12px', color: 'var(--text-secondary)', display: 'block', marginBottom: '4px'}}>
                Telegram Bot Token
              </label>
              <input type="text" disabled placeholder="Set via QP_TELEGRAM_BOT_TOKEN env var"
                     style={{width: '100%', padding: '8px 12px', borderRadius: '6px', border: '1px solid var(--border)', background: 'var(--bg)', color: 'var(--text-secondary)', fontSize: '13px'}} />
            </div>
            <div>
              <label style={{fontSize: '12px', color: 'var(--text-secondary)', display: 'block', marginBottom: '4px'}}>
                Telegram Chat ID
              </label>
              <input type="text" disabled placeholder="Set via QP_TELEGRAM_CHAT_ID env var"
                     style={{width: '100%', padding: '8px 12px', borderRadius: '6px', border: '1px solid var(--border)', background: 'var(--bg)', color: 'var(--text-secondary)', fontSize: '13px'}} />
            </div>
            <div style={{fontSize: '12px', color: 'var(--text-secondary)', background: 'var(--bg)', padding: '10px', borderRadius: '6px', border: '1px solid var(--border)'}}>
              Configure via environment variables. Set QP_TELEGRAM_BOT_TOKEN and QP_TELEGRAM_CHAT_ID
              in your .env file or system environment, then restart the server.
            </div>
          </div>
        </div>
      </div>

      <div className="card">
        <h3>Audit Trail</h3>
        <div style={{display: 'flex', gap: '12px', marginBottom: '12px', alignItems: 'center', flexWrap: 'wrap'}}>
          <input type="text" placeholder="Filter by event type..."
                 value={eventFilter} onChange={e => setEventFilter(e.target.value)}
                 style={{padding: '6px 12px', borderRadius: '6px', border: '1px solid var(--border)', background: 'var(--card-bg)', color: 'var(--text)', fontSize: '13px', width: '200px'}} />
          <input type="date" value={dateFrom} onChange={e => setDateFrom(e.target.value)}
                 style={{padding: '6px 12px', borderRadius: '6px', border: '1px solid var(--border)', background: 'var(--card-bg)', color: 'var(--text)', fontSize: '13px'}} />
          <span style={{color: 'var(--text-secondary)', fontSize: '12px'}}>to</span>
          <input type="date" value={dateTo} onChange={e => setDateTo(e.target.value)}
                 style={{padding: '6px 12px', borderRadius: '6px', border: '1px solid var(--border)', background: 'var(--card-bg)', color: 'var(--text)', fontSize: '13px'}} />
          <button className="btn btn-sm" onClick={exportCSV}
                  style={{background: 'var(--border)', color: 'var(--text)'}}>
            Export CSV
          </button>
          <span style={{fontSize: '12px', color: 'var(--text-secondary)'}}>
            {filteredEvents.length} events
          </span>
        </div>
        <div style={{maxHeight: '400px', overflowY: 'auto'}}>
          <table>
            <thead>
              <tr><th>Time</th><th>Type</th><th>Source</th><th>Details</th></tr>
            </thead>
            <tbody>
              {filteredEvents.slice(0, 100).map((e, i) => (
                <tr key={i}>
                  <td style={{fontSize: '12px', whiteSpace: 'nowrap'}}>{e.timestamp || ''}</td>
                  <td>
                    <span className={'badge badge-' + (e.event_type?.includes('kill') ? 'danger' : e.event_type?.includes('error') ? 'warning' : 'info')}>
                      {e.event_type}
                    </span>
                  </td>
                  <td style={{fontSize: '12px'}}>{e.source}</td>
                  <td style={{fontSize: '12px', color: 'var(--text-secondary)', maxWidth: '300px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap'}}>
                    {e.details || e.message || ''}
                  </td>
                </tr>
              ))}
              {filteredEvents.length === 0 && (
                <tr><td colSpan="4" style={{textAlign: 'center', color: 'var(--text-secondary)'}}>No events matching filters</td></tr>
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
