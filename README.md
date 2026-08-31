# AETMS Trading System

AI-Enhanced Trend & Momentum Strategy (AETMS)

[![CI](https://github.com/your-org/your-repo/actions/workflows/ci.yml/badge.svg)](https://github.com/your-org/your-repo/actions)

Description
-----------
Institutional-grade trading system skeleton combining market data ingestion, AI-driven signals, risk management, and broker adapters (MT5, Binance). The repository contains the Python engine, MQL5 bridge, DB schema, Docker Compose, and docs.

**Architecture**

```mermaid
flowchart LR
  Data[Market Data (CCXT / MT5)] --> AI[AI Signals (KAMA/RSI/ATR + Sentiment)]
  AI --> Risk[Risk Manager (1% per trade, kill-switch)]
  Risk --> Exec[Execution Adapters (MT5 ZeroMQ / Binance CCXT / OANDA REST)]
  Exec --> DB[Postgres Ledger & Events]
  DB --> Grafana[Grafana Monitoring]
  AI --> Alerts[Telegram Alerts]
```

Quick Start
-----------

1. Clone the repo

	```bash
	git clone git@github.com:your-org/your-repo.git
	cd your-repo
	```

2. Copy environment template and fill secrets

	```bash
	cp .env.example .env
	# Edit .env to set POSTGRES_* , TELEGRAM_BOT_TOKEN, BINANCE keys, etc.
	```

3. Run tests

	```bash
	make test
	```

4. Run the bot locally

	```bash
	make run
	```

5. Run with Docker Compose

	```bash
	docker-compose up --build
	```

Documentation
-------------

- Strategy details: [docs/STRATEGY.md](docs/STRATEGY.md)
- Deployment guide: [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md)
- Audit log and traceability: [docs/AUDIT_LOG.md](docs/AUDIT_LOG.md)
- Standard operating procedures: [docs/SOP.md](docs/SOP.md)

Contributing & CI
------------------

This repository uses GitHub Actions to run tests and linting on push and pull requests to `main`. Ensure your branch passes `make test` and `make lint` before opening a PR.

