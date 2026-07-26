#!/usr/bin/env bash
set -e

echo "================================================"
echo "  AI Quant Trading Platform — Setup"
echo "================================================"
echo ""

# Step 1: Python virtual environment
if [ ! -d ".venv" ]; then
    echo "[1/4] Creating Python virtual environment..."
    python3 -m venv .venv
else
    echo "[1/4] Python venv already exists, skipping."
fi

echo "[2/4] Installing Python dependencies..."
.venv/bin/pip install --upgrade pip -q
.venv/bin/pip install -r requirements.txt -q

# Step 2: Dashboard dependencies
if [ -d "dashboard" ]; then
    echo "[3/4] Installing dashboard (React) dependencies..."
    cd dashboard && npm install --silent 2>/dev/null && cd ..
else
    echo "[3/4] No dashboard folder found, skipping."
fi

# Step 3: Environment file
if [ ! -f ".env" ]; then
    echo "[4/4] Creating .env from .env.example..."
    cp .env.example .env
    echo "     IMPORTANT: Edit .env and fill in your API keys/tokens."
else
    echo "[4/4] .env already exists, skipping."
fi

echo ""
echo "================================================"
echo "  Setup complete!"
echo "================================================"
echo ""
echo "Next steps:"
echo "  1. Edit .env with your API keys (Angel One, TradingView, etc.)"
echo "  2. Start the backend:"
echo "     source .venv/bin/activate"
echo "     uvicorn quant_platform.api.app:app --host 0.0.0.0 --port 8000"
echo "  3. Start the dashboard:"
echo "     cd dashboard && npm start"
echo "  4. Open http://localhost:3000 for the dashboard"
echo "  5. POST http://localhost:8000/ingest/start to begin"
echo ""
echo "See QUANT_PLATFORM_CONTEXT.md for full architecture docs."
