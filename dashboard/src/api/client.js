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

  events: (limit = 100) => fetchJSON(`/events/recent?limit=${limit}`),

  ingestStatus: () => fetchJSON('/ingest/status'),
  ingestStart: (profile) => postJSON(`/ingest/start?profile=${profile}`),
  ingestStop: () => postJSON('/ingest/stop'),
  ingestErrors: () => fetchJSON('/ingest/errors'),

  profiles: () => fetchJSON('/profiles'),
  profile: (name) => fetchJSON(`/profiles/${name}`),

  assets: (params = '') => fetchJSON(`/assets?${params}`),
  ohlcv: (assetId, limit = 500) => fetchJSON(`/assets/${assetId}/ohlcv?limit=${limit}`),

  strategies: (status = '') => fetchJSON(`/strategies${status ? `?status=${status}` : ''}`),
  strategy: (id) => fetchJSON(`/strategies/${id}`),
  backtests: (strategyId) => fetchJSON(`/strategies/${strategyId}/backtests`),

  scoringRank: () => fetchJSON('/scoring/rank'),
  scoringStrategy: (id) => fetchJSON(`/scoring/${id}`),

  portfolios: () => fetchJSON('/portfolios'),
  positions: (portfolioId) => fetchJSON(`/portfolios/${portfolioId}/positions`),
  trades: (portfolioId) => fetchJSON(`/portfolios/${portfolioId}/trades`),

  researchStatus: () => fetchJSON('/research/status'),
  researchStart: (profile, topN) => postJSON(`/research/start?profile=${profile}&top_n=${topN}`),
  researchStop: () => postJSON('/research/stop'),

  tradingStatus: () => fetchJSON('/trading/status'),
  tradingStart: (params) => postJSON(`/trading/start?portfolio_name=${params.name}&initial_capital=${params.capital}&interval=${params.interval}`),
  tradingStop: () => postJSON('/trading/stop'),

  riskHealth: () => fetchJSON('/risk/health'),
  correlation: () => fetchJSON('/risk/correlation'),
  stressTest: (regime) => fetchJSON(`/risk/stress-test?regime=${regime}`),
  promoteDemote: () => postJSON('/risk/promote-demote'),
};
