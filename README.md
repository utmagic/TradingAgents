# TradingAgents Web

Web-first TradingAgents system with:
- Backend: FastAPI (`web/backend`)
- Frontend: React + MUI + Vite (`web/frontend`)
- Persistence: SQLite (`web/tradingagents_web.db`)

## Run

### 1) Backend
```bash
cd web/backend
uvicorn web.backend.main:app --reload --host 0.0.0.0 --port 8005
```

### 2) Frontend
```bash
cd web/frontend
npm install
npm run dev -- --host 0.0.0.0 --port 5175
```

## Environment

- Primary backend env file: `web/backend/.env`
- Optional fallback: project root `.env`

Set required API keys (example):
- `OPENAI_API_KEY`
- `GOOGLE_API_KEY`
- `ANTHROPIC_API_KEY`

## Architecture

- Agent runtime is embedded under `web/backend/embedded`.
- Web backend does not import from the removed legacy `tradingagents` or `cli` folders.

## Notes

- Reports are written under `reports/`.
- Saved tickers, runs, events, model catalog/defaults are stored in SQLite.
