# Roadmap

## Completed

### Phase 0A — Agent Engineering Measurement & Evidence Framework (DONE)
Evidence framework, telemetry models, metrics calculator. 96 tests.

### Phase 0 — Greenfield Architecture & Local Foundation Design (DONE)
SQLite schema v0, domain models (Pydantic), config management, ADR-001,
project scaffold, README. 157 tests. SQLite will be replaced by PostgreSQL
in Phase 1.

## Phase 1 — Platform Foundation

| ID | Deliverable | Done Criterion |
|----|-------------|----------------|
| 1.1 | PostgreSQL + Alembic | Local PG running, migrations applied, models use SQLAlchemy |
| 1.2 | FastAPI skeleton | Health check endpoint, app entry point, startup/shutdown lifecycle |
| 1.3 | Plugin interfaces | BrokerAdapter, ResearchSource, LLMProvider abstract base classes |
| 1.4 | LLM abstraction | ClaudeAdapter + OllamaAdapter, configurable per agent role |
| 1.5 | Kill switch service | Separate process, heartbeat watchdog, API/CLI/Telegram triggers |
| 1.6 | Run mode | LOCAL (batch + stop) vs SERVER (continuous), single config flag |
| 1.7 | Structured logging | JSON logs, audit trail, no secrets in output |
| 1.8 | Activity event bus | All system events published to central bus for dashboard consumption |

## Phase 2 — Market Data & Backtesting Engine

| ID | Deliverable | Done Criterion |
|----|-------------|----------------|
| 2.1 | OHLCV data ingestion service | Autonomous FastAPI background service — starts, fetches, retries, recovers on its own. POST /ingest/start kicks off, GET /ingest/status returns progress. 20 years daily OHLCV via configurable data providers (yfinance first). Config-driven — switch to crypto (Binance/CoinGecko), commodities (MCX), or any market by adding a market profile. ~2.5M rows initial load for NSE. Zero token cost while running |
| 2.1b | Historical data store | Full historical OHLCV cached in DB, never re-fetched. Only incremental daily delta pulled. Adjusted close prices handle splits/bonuses/dividends. Same DB works local and production |
| 2.1c | Instrument registry | Config-driven master list of tradeable instruments. Default: NIFTY 500 + 3 indexes (~503). Add crypto pairs, commodity contracts, or any new market via config — no code changes. Filterable by market/sector/cap/volume |
| 2.1d | Market profile system | YAML/JSON config per market: NSE (equities+F&O), crypto (BTC/ETH/alts), MCX (gold/silver/crude), US stocks, etc. Each profile defines: data provider, instruments list, trading hours, fee structure, lot sizes, tick sizes, holidays. Switch markets by changing one config value |
| 2.2 | Strategy model | Provenance, source, license, parameters, version tracking |
| 2.3 | Backtesting engine | VectorBT MIT, reproducible results, stored per strategy |
| 2.4 | Strategy scoring | Sharpe, max drawdown, win rate, profit factor, optimal SL, position size — auto-ranked |
| 2.4b | Fee-aware scoring | Every backtest and score includes broker fees (commission, STT, GST, stamp duty, exchange charges). Net profit AFTER all fees is the real score. Strategy that wins gross but loses net = rejected |
| 2.5 | Backtest results API | REST endpoints serving backtest results for dashboard |

## Phase 3 — Research Source Integration

| ID | Deliverable | Done Criterion |
|----|-------------|----------------|
| 3.1 | ResearchSource interface | Generic adapter pattern, TradingView is first implementation |
| 3.2 | TradingView adapter | Pull strategies from premium account, import Pine scripts |
| 3.3 | Autonomous research engine | Self-contained background service that runs the ENTIRE research pipeline autonomously. Once started, it imports strategies, backtests, scores, shortlists, stress-tests, and generates new strategies — all without Claude intervention. Claude reviews logs every hour, corrects course only if errors or bad decisions detected |
| 3.3a | Research pipeline stages | The engine runs these stages in order, autonomously: (1) Import strategies from configured sources (2) Backtest each against all instruments (3) Score with fee-aware metrics (4) Position sizing + SL calibration + drawdown threshold (5) Winner shortlisting at 80%+ (6) Portfolio stress test across 3 regimes (7) Correlation matrix — reject correlated (8) Deep historical mining (9) Strategy combination — genetic evolution (10) New strategy generation (11) Pine Script export for winners (12) Log everything with full reasoning |
| 3.3b | Research API endpoints | GET /research/status — current stage, strategies processed, winners found, errors. GET /research/logs — structured JSON logs of every decision with reasoning. GET /research/winners — current shortlist. POST /research/start — kick off full pipeline. POST /research/stop — graceful stop. All dashboard-ready |
| 3.3c | Research error recovery | Auto-retry on transient failures (API timeouts, data gaps). Skip and log permanently bad instruments. Never crash the pipeline — isolate failures per strategy/instrument. Structured error log with severity levels for Claude review |
| 3.4 | Multi-instrument backtesting | Run each strategy against indexes AND individual stocks, not just NIFTY/BANKNIFTY |
| 3.5 | Position sizing analysis | Research determines optimal position size per strategy per instrument based on volatility, capital, risk tolerance |
| 3.6 | Stop loss calibration | Research calculates optimal stop loss levels per strategy per instrument from historical price action and ATR |
| 3.7 | Max drawdown threshold | Research sets max acceptable drawdown per strategy — exceeded = auto-reject as loser |
| 3.8 | Winner shortlisting | 80%+ win rate + acceptable drawdown + viable position size + stop loss + NET profitable after all fees = qualified for paper trading |
| 3.9 | Portfolio stress test | Run all winning strategies TOGETHER against historical data. Test 3 market regimes: bullish, bearish, sideways. Find days when all fail together (correlated drawdown), all pass together, and mixed results. Reject portfolio if correlated failure exceeds threshold — strategies must complement each other, not all crash at once |
| 3.10 | Regime analysis | Classify historical periods as bullish/bearish/sideways. Show per-strategy and combined portfolio performance in each regime. Dashboard shows: "in a crash like Mar 2020, your portfolio would have done X" |
| 3.11 | Correlation matrix | Measure strategy-to-strategy return correlation. Flag if too many strategies are correlated (all win/lose together = no diversification). Recommend mix of uncorrelated strategies for true portfolio protection |
| 3.12 | Continuous research loop | Research is NOT one-time. Runs continuously: discover new strategies from TradingView, re-evaluate existing winners against fresh data, retire stale strategies. In LOCAL mode runs every batch cycle, in SERVER mode runs on configurable schedule |
| 3.13 | Deep historical strategy mining | Exhaustively test ALL winning strategies against FULL historical data (years, not days). Every combination of parameters, timeframes, instruments. Find patterns that work across decades, not just recent months. The deeper the data, the more robust the strategy |
| 3.14 | Strategy combination engine | Systematically combine winning strategies — every permutation. Momentum+mean-reversion, breakout+volume, trend+oscillator. Test regime-switching hybrids. Genetic-style evolution: mutate parameters, crossover strategies, survive only if they beat parents on full historical data |
| 3.15 | Optimal strategy generator | Create entirely NEW strategies from research findings. Not just combining existing ones — discover new entry/exit rules, new indicator combinations, new regime filters. These are original IP that can be published and sold on TradingView |
| 3.16 | Strategy export (Pine Script) | Convert winning generated strategies back to Pine Script format for publishing on TradingView marketplace. Include full backtest proof, parameter documentation, performance stats |
| 3.17 | Strategy IP tracking | Track which strategies are original creations vs imported. Mark generated strategies as publishable. Record full research lineage for IP documentation |
| 3.18 | Strategy evolution tracker | Track lineage: strategy X was born from combining Y+Z, which itself was derived from TradingView source W. Full genealogy visible on dashboard |
| 3.19 | Research activity log | Every research action logged: what was pulled, scored, why selected/rejected with position/SL/drawdown/stress test reasoning. Structured JSON for Claude review |

## Phase 4 — Broker Integration & Paper Trading

| ID | Deliverable | Done Criterion |
|----|-------------|----------------|
| 4.1 | BrokerAdapter interface | Generic: place/cancel/status/positions/balance, any market. Must expose fee schedule so scoring engine uses actual broker fees |
| 4.2 | First broker adapter | User's chosen broker, paper trading mode |
| 4.3 | Paper trading engine | Real market data, simulated execution, P&L tracking |
| 4.4 | Order management | Order lifecycle with kill switch check before every action |
| 4.5 | Trade decision log | Every decision: signal in, agent reasoning, action taken, result |

## Phase 5 — Trading Agents & Automation

| ID | Deliverable | Done Criterion |
|----|-------------|----------------|
| 5.1 | Trading agents | LLM-powered, model-agnostic, execute signals autonomously |
| 5.2 | Alert processing | TradingView webhook → agent → broker pipeline |
| 5.3 | Promotion pipeline | Paper N days + 80%+ win rate → real trading (configurable) |
| 5.4 | Position management | Open, scale, close positions based on strategy signals |
| 5.5 | Agent activity feed | Real-time: what each bot is doing, watching, executing |

## Phase 6 — Review, Risk & Self-Improvement

| ID | Deliverable | Done Criterion |
|----|-------------|----------------|
| 6.1 | Risk engine | Position limits, daily loss cap, drawdown triggers |
| 6.2 | Kill switch integration | Every agent checks state before every action |
| 6.3 | Performance monitor | Detect underperforming strategies automatically |
| 6.4 | Review agent | Analyze losses, suggest parameter changes, safeguard capital |
| 6.5 | Auto-adjust | Tighten stops, reduce size, demote losers to paper |
| 6.6 | Strategy rotation | Continuously promote winners, demote losers, feed demoted strategies back to research for combination/improvement |
| 6.7 | Review transparency log | What was flagged, what was recommended, before/after comparison |

## Phase 7 — Command Center Dashboard

The dashboard is the user's ONLY interface to the system. It must provide
complete transparency into every decision the system makes.

**UI Framework:** React + Recharts/Lightweight Charts (TradingView open-source charting library).
All data presented as interactive charts and graphs — no raw tables or text dumps.
User must be able to click, zoom, filter, drill down into any data point.

**Dashboard hierarchy — no clutter, separate views per context:**
- **Home / Portfolio Overview** — high-level: total P&L, active strategies count, system health, kill switch status. One glance = am I making money, is everything running
- **Per-Market dashboards** — separate dashboard per active market profile (NSE Equity, NSE F&O, Crypto, Commodities). Each market has its own research, strategies, P&L, bots
- **Per-Index dashboards** — within NSE: separate views for NIFTY 50, BANKNIFTY, FINNIFTY. Each shows strategies running on that index, backtest results, paper/live P&L
- **Per-Stock dashboards** — click any stock from the instrument list to see its dedicated page: price chart, strategies tested on it, active positions, historical performance
- **Strategy detail page** — one page per strategy: backtest equity curve, parameter history, promotion timeline, trades list, fee breakdown
- **Comparison view** — side-by-side any two strategies, stocks, or indexes. Overlay charts, diff metrics

Navigation: sidebar with market/index/stock tree. Search bar to jump to any instrument or strategy. Breadcrumbs for context. No page shows more than one market's data unless user explicitly opens comparison view.

**Visual standards:**
- Candlestick charts for price data (zoomable, with volume bars below)
- Equity curves as line charts with drawdown shading
- Win/loss as donut charts + bar charts with 80% threshold line
- Heatmaps for correlation matrix and regime performance
- Sankey/flow diagrams for strategy lifecycle (discovered → backtested → paper → promoted → demoted)
- Sparklines for quick glance metrics in cards
- Color coding: green = profit/winner, red = loss/loser, amber = under review
- Dark/light theme toggle
- Responsive: works on desktop and tablet for monitoring on the go

### 7A — Research & Strategy Intelligence

| ID | Deliverable | Done Criterion |
|----|-------------|----------------|
| 7A.1 | Research pipeline view | Interactive Kanban board: strategies flowing through discover → backtest → score → shortlist stages. Click any card to see full details |
| 7A.2 | Strategy selection logic | Visual scorecard per strategy: radar chart showing win rate, Sharpe, drawdown, fees, position size. Green/red pass/fail indicators per criterion |
| 7A.3 | Winner/loser breakdown | Bar chart with 80% threshold line, donut chart for win/loss distribution, sortable table with sparklines for each strategy's equity curve |
| 7A.4 | Research activity feed | Live scrolling timeline with icons per action type (import, backtest, score, reject, promote). Filterable by status |

### 7B — Trading Bot Monitor

| ID | Deliverable | Done Criterion |
|----|-------------|----------------|
| 7B.1 | Bot status panel | Card grid with live status badges (idle/watching/executing), animated pulse for active bots, click to expand full bot detail view |
| 7B.2 | Decision trail | Interactive timeline: click any decision node to see signal → reasoning → action → outcome with expandable LLM reasoning text |
| 7B.3 | Order book | Live updating table with status pills (pending=amber, filled=green, cancelled=red), click any order to see full lifecycle |
| 7B.4 | Position tracker | Real-time cards with mini candlestick charts showing entry point marked, current price animated, unrealized P&L as growing/shrinking bar |

### 7C — Portfolio & P&L

| ID | Deliverable | Done Criterion |
|----|-------------|----------------|
| 7C.1 | P&L dashboard | Interactive equity curve chart (zoomable, date range selector: today/week/month/YTD/all). Per-strategy lines overlaid on portfolio total. Hover for exact values |
| 7C.2 | Win/loss ratio | Stacked bar chart per strategy with horizontal 80% threshold line. Overall portfolio donut chart. Click any bar to drill into individual trades |
| 7C.3 | Drawdown monitor | Area chart showing drawdown depth over time with red shading when below threshold. Push alerts on breach |
| 7C.4 | Portfolio confidence | Gauge/meter widget: "N strategies at 80%+ = X% confidence". Monte Carlo simulation fan chart showing probable outcomes |
| 7C.5 | Strategy allocation | Treemap or pie chart showing capital distribution. Click any segment to see that strategy's detail page |

### 7D — Review & Improvement Transparency

| ID | Deliverable | Done Criterion |
|----|-------------|----------------|
| 7D.1 | Flagged strategies | Alert cards with severity badges (critical/warning/info), click to expand full diagnosis and agent reasoning |
| 7D.2 | Review recommendations | Side-by-side comparison panels: current parameters vs recommended changes, with projected impact chart |
| 7D.3 | Before/after comparison | Dual equity curve overlay: before adjustment (faded) vs after (bold). Delta metrics highlighted in green/red |
| 7D.4 | Promotion/demotion history | Visual Sankey/flow diagram: strategies flowing between stages over time. Horizontal timeline with lifecycle events as nodes |

### 7E — Operations & Controls

| ID | Deliverable | Done Criterion |
|----|-------------|----------------|
| 7E.1 | Kill switch controls | Prominent red button with confirmation modal, animated status indicator (armed/disarmed), trigger history timeline |
| 7E.2 | System health | Traffic-light status cards: DB, broker, LLM, heartbeat. Uptime chart. Click any card to see connection logs |
| 7E.3 | Notifications config | Toggle switches for each alert type (Telegram/email), test notification button, delivery history log |
| 7E.4 | Market calendar | Interactive calendar view with NSE holidays, expiry dates, corporate actions highlighted. Click any date to see what ran that day |
| 7E.5 | Audit trail | Searchable, filterable log table with timestamp, agent, action, reason. Export to CSV. Click any row to expand full detail |

## Phase FINAL — End-to-End Validation

Full system test: research → backtest → paper trade → review → promote.
Local mode batch cycle verified. Server mode 24/7 verified.
Kill switch tested under load. All dashboards populated with real data.
Portfolio confidence at 80%+ verified across multiple strategy combinations.

## Sprint Target: Jul 25-27 (Weekend Sprint)

Goal: system built, all historical analysis complete, ready for live paper trading Monday Jul 28.

**Saturday Jul 25 — Build (Claude active, ~400K tokens)**
- Phase 1: Platform foundation (PostgreSQL, FastAPI, plugins, kill switch, event bus)
- Phase 2: Data ingestion service + backtesting engine + market profiles
- Phase 3: Autonomous research engine (builds the service, not runs it)
- Phase 4-6: Broker adapter, trading agents, risk engine, review agent
- Start data ingestion service (POST /ingest/start — runs autonomously)

**Saturday night → Sunday Jul 26 — Autonomous services running (Claude reviews logs hourly, ~10K tokens)**
- Data ingestion service loads 20yr OHLCV + NSE bhav copies (~2.5M rows) — autonomous
- Research engine runs full pipeline autonomously: import → backtest → score → position size → SL → drawdown → shortlist → stress test → regime → correlation → mining → combination → generation
- Claude checks GET /ingest/status and GET /research/status every hour
- Claude reviews GET /research/logs — corrects bad decisions or errors only when found
- If research engine makes a questionable rejection or scoring error, Claude adjusts config and restarts that stage

**Sunday Jul 27 — Dashboard + Review (Claude active, direct writes)**
- Phase 7: Dashboard sections written directly (no parallel agents) while research engine runs
- Research results displayed: winners, losers, stress test charts, correlation heatmap
- Verify all data loaded, all strategies scored, winner shortlist ready

**Monday Jul 28 — Go Live (Paper)**
- Only incremental daily delta fetched (market open data)
- Paper trading begins on shortlisted winners
- System is live and autonomous, user monitors dashboard only

**Token budget:**
- Building (Phases 1-6): ~350K tokens
- Dashboard (Phase 7, direct writes): ~50K tokens
- Hourly log reviews (Saturday night-Sunday): ~10K tokens (20 checks x 500 tokens)
- Course corrections from log review: ~10K tokens (estimated 2-3 fixes)
- **TOTAL: ~420K tokens**

## Data Ingestion Strategy (Hybrid)

| Source | What | Coverage | When |
|--------|------|----------|------|
| yfinance (free, MIT) | Daily OHLCV equity + indexes | 20 years, NIFTY 500 + 3 indexes | Initial bulk load Saturday-Sunday |
| NSE bhav copies (free) | F&O contracts (futures + options) | As far back as available (~15-17 years) | Initial bulk load Saturday-Sunday |
| Broker API (free with account) | Recent F&O + real-time quotes | 1-5 years depending on broker | After broker adapter connected |
| CoinGecko/Binance API (free) | Crypto OHLCV (BTC, ETH, alts) | Full available history | When crypto market profile activated |
| MCX data provider | Commodity OHLCV (gold, silver, crude) | Available history | When commodity market profile activated |
| Daily snapshots | All instruments across all active market profiles | From Monday onwards | Automated daily job |

All data stored in PostgreSQL, never re-fetched. Only daily incremental delta from Monday.

**Ingestion service is autonomous** — once started, it fetches, retries, rate-limits, and recovers on its own. Claude only checks GET /ingest/status once per hour to verify completion. Zero token cost while data loads.

## Design Principles

1. Local-first: runs completely on your laptop, same code deploys to server
2. Plugin everything: brokers, research sources, LLM providers all swappable
3. Kill switch is sacred: separate process, always armed in real trading
4. Paper before real: every strategy must prove itself in paper trading first
5. Self-improving: system reviews performance, combines winners into hybrid strategies, continuously discovers new opportunities
6. Model-agnostic: works with Claude, Ollama, any LLM
7. Market-agnostic: stocks today, crypto tomorrow, same interfaces
8. Full transparency: every decision visible on dashboard, nothing is a black box
9. 80% win threshold: strategy must hit 80%+ win rate to qualify for real money
10. Portfolio diversification: multiple strategies running = higher probability of overall profit
11. Fee-aware everything: all scores, rankings, and decisions use NET profit after broker fees. A strategy that costs more to execute than it earns is automatically rejected
