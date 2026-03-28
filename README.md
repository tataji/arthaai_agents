# ArthAI — Agentic AI Trading System for Indian Markets

A production-grade agentic trading system for NSE/BSE powered by Claude AI (Anthropic), Zerodha Kite Connect, and a multi-agent architecture.

---

## Architecture

```
arthaai/
├── main.py                    # Entry point — starts all agents
├── config.py                  # API keys, broker config, risk params
├── agents/
│   ├── orchestrator.py        # Master agent — coordinates all sub-agents
│   ├── technical_agent.py     # Technical analysis (RSI, MACD, BB, patterns)
│   ├── fundamental_agent.py   # Fundamental screener (PE, ROE, FII/DII)
│   ├── news_agent.py          # News & sentiment analysis via Claude
│   ├── risk_agent.py          # Risk management & position sizing
│   └── fo_agent.py            # F&O strategy agent (options Greeks)
├── strategies/
│   ├── momentum.py            # Momentum strategy
│   ├── mean_reversion.py      # Mean reversion strategy
│   ├── breakout.py            # Breakout strategy
│   └── options_strategies.py  # Iron Condor, Bull Call Spread, etc.
├── data/
│   ├── market_data.py         # Zerodha Kite live data feed
│   ├── nse_scraper.py         # NSE website scraper (FII/DII, OI)
│   └── database.py            # SQLite for trade history & logs
├── utils/
│   ├── indicators.py          # Technical indicator calculations
│   ├── notifications.py       # Telegram/email alerts
│   └── logger.py              # Structured logging
├── frontend/                  # React dashboard (see frontend/README.md)
├── requirements.txt
└── .env.example
```

---

## Quick Start

### 1. Install dependencies
```bash
pip install -r requirements.txt
```

### 2. Configure environment
```bash
cp .env.example .env
# Edit .env with your API keys
```

### 3. Run in paper-trading (safe) mode
```bash
python main.py --mode paper
```

### 4. Run in live mode (real money — use with caution)
```bash
python main.py --mode live
```

---

## Broker Setup (Zerodha Kite Connect)

1. Create an app at https://developers.kite.trade
2. Get your `api_key` and `api_secret`
3. Run `python utils/auth.py` to get your `access_token` each morning
4. Add credentials to `.env`

---

## Risk Disclaimer

This software is for educational and research purposes. Trading in Indian equity and F&O markets involves significant financial risk. Past performance of any algorithm does not guarantee future results. Always test thoroughly in paper-trading mode before using real capital. The authors are not responsible for any financial losses.

---

## License
MIT
