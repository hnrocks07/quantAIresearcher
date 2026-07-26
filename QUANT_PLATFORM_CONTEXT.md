# AI Quant Autonomous Trading Platform — Complete Build Context

This file contains ALL discussions, decisions, architecture, requirements, and build state for the quant platform. Portable — carry to any machine and resume work with full context.

---

## 1. VISION & CORE REQUIREMENTS

The platform must be FULLY AUTONOMOUS. User does NOT trade manually. AI agents do all research, backtesting, paper trading, and real trading. User only looks at dashboards.

- One button press starts everything: ingest → research → TV discovery → paper trade → promote → real trade
- Alerts are NOT "notify user to act" — they are "agent acts, notifies user what happened"
- Strategies self-improve without user input
- Kill switch is the only manual override (plus dashboard review)
- Indian markets first (NSE indexes + stocks), crypto later
- 80% win rate threshold for promotion from paper to real
- Fee-aware everything: all backtests use NET profit after broker fees
- Historical data cached in DB, only daily incremental delta fetched — never re-pull
- Research is CONTINUOUS, not one-time
- Combine winning strategies into hybrids: genetic evolution, crossover, mutate
- Generate entirely NEW original strategies — these are sellable IP
- Export generated strategies to Pine Script for TradingView marketplace
- Track strategy lineage/genealogy: which strategies were born from combining others

---

## 2. ARCHITECTURE — PLUG-AND-PLAY

Everything swappable via QP_ env vars, nothing hardcoded:

- **Broker:** Angel One (default) via BrokerAdapter interface. Swap to Zerodha, IBKR, Alpaca by changing QP_BROKER_ADAPTER
- **Research:** TradingView (default) via ResearchSource interface. Authenticated login for premium scripts
- **LLM:** Claude Sonnet (default) via LLMProvider interface. Swap to Ollama, GPT, Gemini
- **Data:** 6 providers via DataProvider interface: yfinance, nse_bhav, jugaad_nse, crypto, indstocks, nsedata
- All adapters loaded via PluginRegistry from config

4 plugin ABCs: BrokerAdapter, ResearchSource, DataProvider, LLMProvider

---

## 3. TECH STACK

- Python 3.14+, FastAPI, SQLAlchemy 2.0, Alembic, PostgreSQL (SQLite for tests)
- Pydantic v2, pydantic-settings with QP_ env prefix
- React + Recharts dashboard with dark theme, HTTP polling at 2-5s intervals
- Angel One SmartAPI (smartapi-python, pyotp for TOTP auth)
- TradingView: tradingview_ta for TA signals, authenticated session for premium community scripts
- jugaad-data for NSE F&O bhav copy data
- INDstocks API for 5m/15m intraday candles (free, no subscription)
- NSE-Data CSV for 20-year historical intraday data (auto-downloaded from Google Drive via gdown)
- gdown for Google Drive auto-downloads
- All open source, no paid APIs

---

## 4. BUILD STATUS (26 Jul 2026)

**Location:** ~/Downloads/AI_Quant_AgentTeam_Proof_ProductionGrade_Bootstrap/
**Git:** branch feature/phase-2-to-7, latest commit 30199dc
**Tests:** 205 passing

**File counts:** 59 Python files, 12 React files, 49+ API endpoints

### Phase Completion:
- Phase 1 (Foundation): 8/8 = 100% — PostgreSQL, FastAPI, plugins, kill switch, event bus, run modes
- Phase 2 (Data): 5/5 = 100% — Pluggable providers, F&O fields, market profiles, fee-aware scoring
- Phase 3 (Research): 15/17 = 88% — Engine, TV source, combinations, lineage, Pine export, regime analysis
- Phase 4 (Broker): 4/4 = 100% — Angel One adapter, trade decision log
- Phase 5 (Agents): 5/5 = 100% — LLM agents, promotion pipeline, position scaling
- Phase 6 (Risk): 7/7 = 100% — Daily loss cap, position limits, performance monitor, auto-adjust, rotation
- Phase 7 (Dashboard): 100% — All 5 pages (7A-7E) + AgentMonitor

### 2 Remaining Partial Items (Phase 3):
1. Per-strategy drawdown threshold — DD tracked but no auto-trigger on breach
2. Error retry with backoff — catch-and-skip only, no exponential retry

**Overall: ~96% complete**

---

## 5. DATA PROVIDERS (6 total)

| Provider | Source | Intervals | History | Auto-Update | Free |
|----------|--------|-----------|---------|-------------|------|
| yfinance | Yahoo Finance | 1d | 20 years | No | Yes |
| nse_bhav | NSE bhav copy | 1d | varies | No | Yes |
| jugaad_nse | jugaad-data | 1d, F&O | 15 years | No | Yes |
| crypto | CoinGecko | 1d | 10 years | No | Yes |
| indstocks | INDstocks API | 5m,15m,1h,1d | 7d chunks | Daily auto | Yes (free account) |
| nsedata | NSE-Data CSV | 1m-1d all | 20 years | No (static) | Yes |

### Intraday Setup (added 26 Jul 2026):
- OHLCV model has interval column (default "1d"), UniqueConstraint on (asset_id, date, interval)
- INDstocksProvider: 7-day chunked fetches, rate limited, Nifty 50 scrip codes
- NSEDataProvider: auto-downloads 6.5GB from Google Drive on first connect, Nifty 50 + Next 50 + NIFTY 50 index + BANKNIFTY index
- Daily auto-update in SERVER mode at QP_AUTO_UPDATE_TIME IST (default 15:45), skips weekends
- Market profile: nse_intraday.json for scalping

---

## 6. KEY FILES & STRUCTURE

**Core Platform:**
- src/quant_platform/config.py — Settings with QP_ env prefix
- src/quant_platform/models.py — All SQLAlchemy ORM models + Pydantic schemas
- src/quant_platform/database.py — Engine, session, Base
- src/quant_platform/api/app.py — FastAPI with 49+ endpoints
- src/quant_platform/plugins/ — ABCs: broker.py, research.py, data_provider.py, registry.py
- src/quant_platform/kill_switch.py — Kill switch with heartbeat watchdog
- src/quant_platform/event_bus.py — Central event bus for dashboard consumption

**Data Layer:**
- src/quant_platform/data/ingestion.py — Autonomous ingestion + auto-pipeline + daily scheduler
- src/quant_platform/data/yfinance_provider.py — YFinance daily data
- src/quant_platform/data/jugaad_provider.py — F&O bhav copy via jugaad-data
- src/quant_platform/data/indstocks_provider.py — INDstocks 5m/15m intraday
- src/quant_platform/data/nsedata_provider.py — Bulk CSV with Google Drive auto-download
- src/quant_platform/data/nse_provider.py — NSE bhav copy
- src/quant_platform/data/crypto_provider.py — CoinGecko top 20 cryptos
- src/quant_platform/data/backtesting.py — BacktestEngine
- src/quant_platform/data/scoring.py — Fee-aware scoring + ranking

**Research Layer:**
- src/quant_platform/research/engine.py — ResearchEngine: backtest, score, combine, enrich
- src/quant_platform/research/tradingview_source.py — TV authenticated login + premium scripts + multi-TF TA
- src/quant_platform/research/combination.py — BestOfBestFinder: 2-way AND/OR + 3-way majority vote
- src/quant_platform/research/lineage.py — Strategy evolution tracking
- src/quant_platform/research/strategies.py — 5 built-in strategies + parameter grid
- src/quant_platform/research/regime.py — Bull/bear/sideways classification
- src/quant_platform/research/pine_export.py — Export to Pine Script
- src/quant_platform/research/position_sizing.py — ATR-based position sizing
- src/quant_platform/research/stop_loss.py — Optimal stop loss calculation
- src/quant_platform/research/activity_log.py — Structured research activity log

**Trading Layer:**
- src/quant_platform/trading/executor.py — Full trading loop: loss check → limits → LLM → trade → promote → review → rotate
- src/quant_platform/trading/paper_broker.py — Paper trading simulator
- src/quant_platform/trading/angel_broker.py — Angel One SmartAPI adapter
- src/quant_platform/trading/promotion.py — PromotionManager: paper → real
- src/quant_platform/trading/decision_log.py — Trade decision audit trail

**Risk & Agents:**
- src/quant_platform/risk/ — DailyLossMonitor, PositionLimiter, PerformanceMonitor, AutoAdjuster, StrategyRotator, ReviewLog
- src/quant_platform/agents/ — SignalAgent, DecisionAgent, ReviewAgent, PositionScaler, ActivityFeed
- src/quant_platform/llm_adapters/ — ClaudeAdapter, OllamaAdapter

**Market Profiles:**
- src/quant_platform/market_profiles/configs/nse_equity.json — 20yr daily, Nifty 500
- src/quant_platform/market_profiles/configs/nse_fno.json — 15yr F&O, jugaad_nse
- src/quant_platform/market_profiles/configs/nse_intraday.json — 1yr intraday scalping, indstocks
- src/quant_platform/market_profiles/configs/crypto.json — 10yr crypto

**Dashboard (React):**
- dashboard/src/pages/Overview.jsx — P&L equity curve, win/loss bars, drawdown, gauge, treemap
- dashboard/src/pages/Research.jsx — Kanban board, radar scorecard, 80% threshold
- dashboard/src/pages/Trading.jsx — Bot grid, decision timeline, sparklines, promotion bars
- dashboard/src/pages/Risk.jsx — Flagged cards, review recs, correlation heatmap, flow diagram
- dashboard/src/pages/KillSwitch.jsx — Traffic lights, NSE 2026 calendar, audit trail CSV export
- dashboard/src/pages/AgentMonitor.jsx — Agent cards, scrolling activity feed, filters

---

## 7. AUTONOMOUS PIPELINE FLOW

1. POST /ingest/start triggers data ingestion
2. After ingestion completes → _auto_start_research() fires automatically
3. Research engine starts: imports strategies (built-in + TradingView), backtests all, scores, shortlists winners
4. TradingView continuous discovery starts in background (premium scripts + multi-TF TA on 5m/15m/1h/4h/1d/1w)
5. BestOfBestFinder tests ALL winner pairs (AND+OR modes) + 3-way majority triples
6. Paper trading starts automatically
7. Executor loop runs: daily_loss_check → position_limits → LLM_agents → trade → promotion → performance_review → auto_adjust → rotation
8. Promotion: paper N days + 80% win rate → real trading
9. Strategy lineage tracked: record_lineage() on every combination
10. Everything reports to dashboard via activity_feed and event_bus

---

## 8. CONFIGURATION (.env template)

QP_DB_URL=sqlite:///quant_platform.db
QP_RUN_MODE=local
QP_REAL_TRADING=false
QP_DATA_PROVIDER=yfinance
QP_LLM_PROVIDER=claude
QP_LLM_MODEL=claude-sonnet-4-6
QP_BROKER_ADAPTER=paper
QP_RESEARCH_SOURCE_MODE=both
QP_TRADINGVIEW_USERNAME=
QP_TRADINGVIEW_PASSWORD=
QP_ANGEL_API_KEY=
QP_ANGEL_CLIENT_ID=
QP_ANGEL_PIN=
QP_ANGEL_TOTP_SECRET=
QP_INDSTOCKS_TOKEN=
QP_AUTO_UPDATE_ENABLED=true
QP_AUTO_UPDATE_TIME=15:45
QP_PAPER_TRADING_DAYS_REQUIRED=14
QP_MAX_POSITIONS=20
QP_DAILY_LOSS_CAP_PCT=0.05
QP_PROMOTION_WIN_RATE=0.80
QP_PROMOTION_MIN_TRADES=20

---

## 9. TRADING EXECUTOR — 10 WIRED COMPONENTS

All 10 were built as separate files but were NOT called in the executor. Fixed by rewriting executor.py:

1. DailyLossMonitor — checks daily loss cap, triggers kill switch
2. PositionLimiter — max positions, max per instrument
3. SignalAgent — LLM analyzes market signals
4. DecisionAgent — LLM decides trade action with reasoning
5. ReviewAgent — LLM analyzes losses, suggests parameter changes
6. AutoAdjuster — tightens stops, reduces position size on underperformance
7. StrategyRotator — demotes/requeues underperformers
8. PerformanceMonitor — detects underperforming strategies
9. PromotionManager — evaluates paper strategies for real trading
10. PositionScaler — scales exit sizing

---

## 10. BEST-OF-BEST COMBINATION ENGINE

- combine_strategies() supports mode="and"|"or"|"majority"
- combine_three(): 3-way majority vote (enter when 2 of 3 agree)
- BestOfBestFinder.find_best(): tests ALL winner pairs in AND+OR modes, tests triples from top pair components
- _compute_score(): weighted 25% win_rate + 25% sharpe + 20% profit_factor + 15% net_profit + 15% drawdown
- Tracks beats_all_components flag
- Strategy lineage recorded via record_lineage() for every combination

---

## 11. TRADINGVIEW INTEGRATION

- Authenticated login with QP_TRADINGVIEW_USERNAME/PASSWORD for premium scripts
- 10 search categories: strategy, swing trading, intraday, scalping, trend following, mean reversion, momentum, breakout, RSI strategy, MACD strategy
- Pine Script parsing via regex: extracts SMA/EMA/RSI/MACD/BB/ATR parameters
- Multi-timeframe TA scan: 6 timeframes (5m, 15m, 1h, 4h, 1d, 1w) across 50 NSE symbols
- Continuous discovery loop: run_continuous() runs every N minutes
- Webhook receiver: POST /webhooks/tradingview

---

## 12. MANUAL STRATEGY IMPORT

POST /strategies/import with:
- name (required)
- pine_script (optional — auto-parsed for SMA/EMA/RSI/MACD/BB/ATR params)
- parameters (optional — custom params)
- description, source

Imported strategies enter pipeline as "discovered" → get backtested → scored → promoted like any other.

---

## 13. BUILD RULES (STRICT)

- Everything open source, no paid APIs
- Build in silence — only report phase completions
- Token efficient — small tasks done directly, agents only for large parallel work, agent prompts under 500 words
- Do NOT start data ingestion until user explicitly says so
- Dashboard is the ONLY interface — must show everything transparently
- Credentials as None placeholders, user provides later
- Keep everything local, no remote push unless user says so
- Direct execution preferred over sequential agent pipeline for speed

---

## 14. PARKED ITEMS

1. **WebSocket/SSE** — replace polling with real-time updates when moving to server
2. **Per-strategy drawdown auto-trigger** — DD tracked but no auto-reject on breach
3. **Error retry with backoff** — catch-and-skip only, no exponential retry

---

## 15. HOW TO START

**Automated (recommended):**
1. git clone <repo-url> && cd <repo-name>
2. chmod +x setup.sh && ./setup.sh
3. Edit .env with your API keys
4. source .venv/bin/activate
5. uvicorn quant_platform.api.app:app --host 0.0.0.0 --port 8000
6. cd dashboard && npm start
7. POST /ingest/start — auto-pipeline kicks in after ingestion

**Manual:**
1. pip install -r requirements.txt
2. cp .env.example .env — fill in your tokens
3. uvicorn quant_platform.api.app:app --host 0.0.0.0 --port 8000
4. cd dashboard && npm install && npm start
5. POST /ingest/start — auto-pipeline kicks in after ingestion

**For intraday scalping:**
- POST /ingest/start?profile=nse_intraday&interval=5m (nsedata provider auto-downloads CSVs)
- Or set QP_INDSTOCKS_TOKEN and use indstocks provider for live 5m data

---

## 16. RESUME COMMANDS

- "Resume quant platform" — general resume
- "Fix Phase 3 partial items" — drawdown auto-trigger + error retry
- "Start data ingestion" — begin pulling market data
- "Move to server" — add WebSocket, deploy to VPS
- "Resume intraday data providers" — if intraday work was paused
