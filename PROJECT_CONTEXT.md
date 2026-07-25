# Project Context

## project_name
Local Trading Simulator & Autonomous Trading Platform

## version
0.2.0

## language
Python 3.11+

## storage
PostgreSQL (local-first, same schema on dev machine and production server)

## real_trading
Enabled with safeguards — paper trading required before real money.
Kill switch can halt all trading instantly.

## secrets_policy
All secrets (API keys, broker credentials, LLM keys) loaded from environment
variables or .env file only. Never committed to source control or emitted in logs.

## run_modes
- LOCAL: batch cycle — run research/backtest/paper trade, generate results, stop.
  User reviews dashboards and decides next steps. No persistent daemon.
- SERVER: continuous loop — 24/7 autonomous trading, monitoring, alerts.
  Same codebase, same config, flip RUN_MODE=server.

## plugin_architecture
- BrokerAdapter: generic interface for any broker (stocks, crypto, any market).
  Swap brokers by changing config, not code.
- ResearchSource: generic interface for strategy research platforms.
  TradingView is first adapter, replaceable.
- LLMProvider: generic interface for AI models.
  Claude first, Ollama for open source, LiteLLM for any provider.
  Configurable per agent role.

## kill_switch
Separate process, independent of main app. Triggers:
- Dashboard button, API endpoint, CLI command, Telegram message
- Heartbeat watchdog (auto-trigger if main app unresponsive)
Actions: cancel all orders, disable agents, freeze positions.

## scope_current
- Platform foundation with plugin interfaces
- Market data ingestion (Indian markets: NIFTY, BANKNIFTY, NSE)
- Strategy research pipeline (TradingView premium → backtest → rank)
- Backtesting engine (VectorBT MIT)
- Broker integration (generic, paper + real trading)
- Autonomous trading agents (LLM-powered, model-agnostic)
- Risk management and kill switch
- Performance review and strategy self-improvement
- Dashboard and notifications
- Local-first: runs as batch on dev machine, 24/7 on server

## out_of_scope
- Advanced custom charting / TradingView clone UI
- Building a broker (we connect to existing ones)
- High-frequency trading (we're strategy-level, not tick-level)

## target_environment
- Local: macOS / Linux developer machine, PostgreSQL, Python 3.11+
- Server: any Linux VPS with PostgreSQL, runs 24/7
- Both use identical codebase and config format
