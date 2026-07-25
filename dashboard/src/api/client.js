const BASE = '/api';

async function fetchJSON(path) {
  const res = await fetch(`${BASE}${path}`);
  if (!res.ok) throw new Error(`API error: ${res.status}`);
  return res.json();
}

async function postJSON(path, body = {}) {
  const res = await fetch(`${BASE}${path}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  return res.json();
}

export const api = {
  health: () => fetchJSON('/health'),
  config: () => fetchJSON('/config'),

  killSwitchStatus: () => fetchJSON('/kill-switch/status'),
  killSwitchTrigger: (reason) => postJSON(`/kill-switch/trigger?reason=${encodeURIComponent(reason)}`),
  killSwitchReset: () => postJSON('/kill-switch/reset'),
  killSwitchHeartbeat: () => postJSON('/kill-switch/heartbeat'),

  events: (limit = 100) => fetchJSON(`/events?limit=${limit}`),

  ingestStatus: () => fetchJSON('/ingest/status'),
  ingestStart: (profile) => postJSON(`/ingest/start/${profile}`),
  ingestStop: () => postJSON('/ingest/stop'),
  ingestErrors: () => fetchJSON('/ingest/errors'),

  profiles: () => fetchJSON('/profiles'),
  profile: (name) => fetchJSON(`/profiles/${name}`),

  assets: (params = '') => fetchJSON(`/assets?${params}`),
  ohlcv: (assetId, limit = 500) => fetchJSON(`/assets/${assetId}/ohlcv?limit=${limit}`),

  strategies: (status = '') => fetchJSON(`/strategies${status ? `?status=${status}` : ''}`),
  strategy: (id) => fetchJSON(`/strategies/${id}`),
  backtests: (strategyId) => fetchJSON(`/backtest-results?strategy_id=${strategyId}`),
  backtestResults: () => fetchJSON('/backtest-results'),

  scoringRank: () => fetchJSON('/scoring/rank'),
  scoringStrategy: (id) => fetchJSON(`/scoring/${id}`),

  portfolios: () => fetchJSON('/portfolios'),
  positions: (portfolioId) => fetchJSON(`/positions${portfolioId ? `?portfolio_id=${portfolioId}` : ''}`),
  trades: (portfolioId) => fetchJSON(`/trades${portfolioId ? `?portfolio_id=${portfolioId}` : ''}`),
  allPositions: () => fetchJSON('/positions'),
  allTrades: () => fetchJSON('/trades'),

  researchStatus: () => fetchJSON('/research/status'),
  researchStart: (params) => postJSON('/research/start', params),
  researchStop: () => postJSON('/research/stop'),
  researchErrors: () => fetchJSON('/research/errors'),
  researchActivityLog: () => fetchJSON('/research/activity-log'),

  tradingStatus: () => fetchJSON('/trading/status'),
  tradingStart: (params) => postJSON(`/trading/start?portfolio_name=${params.name}&initial_capital=${params.capital}&interval=${params.interval}`),
  tradingStop: () => postJSON('/trading/stop'),
  tradingPromotionEvaluate: (strategyId) => postJSON(`/trading/promotion/evaluate/${strategyId}`),

  riskHealth: () => fetchJSON('/risk/health'),
  correlation: () => fetchJSON('/risk/correlation'),
  stressTest: (regime) => fetchJSON(`/risk/stress-test/${regime}`),
  dailyLoss: () => fetchJSON('/risk/daily-loss'),
  positionLimits: () => fetchJSON('/risk/position-limits'),
  riskPerformance: (strategyId) => fetchJSON(`/risk/performance/${strategyId}`),
  riskReviewLog: () => fetchJSON('/risk/review-log'),
  riskReview: (strategyId, body) => postJSON(`/risk/review/${strategyId}`, body),
  riskRotate: () => postJSON('/risk/rotate'),
  promoteDemote: () => postJSON('/risk/promote-demote'),

  agentsActivityFeed: () => fetchJSON('/agents/activity-feed'),
  agentActivityFeed: (agentName) => fetchJSON(`/agents/activity-feed/${agentName}`),
};
