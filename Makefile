# Makefile — ArthAI Development & Production Commands

.PHONY: help install dashboard api agents test lint format clean docker docker-up

help:  ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

# ── Setup ──────────────────────────────────────────────────────────────────────
install:  ## Install all Python dependencies
	pip install --upgrade pip
	pip install -r requirements.txt
	pip install -r requirements-dashboard.txt
	pip install pytest ruff black

install-dev:  ## Install with dev extras
	make install
	pip install pytest-cov ipython

# ── Running ─────────────────────────────────────────────────────────────────────
dashboard:  ## Start Streamlit dashboard
	streamlit run dashboard/app.py

dashboard-prod:  ## Start dashboard in production mode
	streamlit run dashboard/app.py \
		--server.port=8501 \
		--server.address=0.0.0.0 \
		--server.headless=true \
		--browser.gatherUsageStats=false

api:  ## Start FastAPI backend
	uvicorn server:app --reload --host 0.0.0.0 --port 8000

agents:  ## Start trading agents (paper mode)
	python main.py --mode paper

agents-live:  ## Start agents (LIVE — real money!)
	@echo "⚠️  Starting in LIVE mode — real money will be used!"
	@read -p "Type YES to confirm: " ans && [ "$$ans" = "YES" ]
	python main.py --mode live

analyse:  ## Analyse a single stock (make analyse SYM=RELIANCE)
	python main.py --analyse $(SYM)

backtest:  ## Run backtest (make backtest SYM=TCS DAYS=365)
	python backtest.py --symbol $(or $(SYM),RELIANCE) --days $(or $(DAYS),365)

auth:  ## Refresh Zerodha access token (run daily before market)
	python utils/auth.py

# ── Testing ──────────────────────────────────────────────────────────────────
test:  ## Run all tests
	pytest tests/ -v

test-cov:  ## Run tests with coverage report
	pytest tests/ -v --cov=. --cov-report=html --cov-report=term-missing
	@echo "Coverage report: htmlcov/index.html"

test-fast:  ## Run only fast unit tests
	pytest tests/ -v -m "not slow"

# ── Code Quality ──────────────────────────────────────────────────────────────
lint:  ## Check code style
	ruff check . --ignore E501

format:  ## Auto-format code
	black .
	isort .

# ── Docker ───────────────────────────────────────────────────────────────────
docker:  ## Build Docker image
	docker build -t arthaai:latest .

docker-up:  ## Start all services with Docker Compose
	docker compose up -d

docker-up-agents:  ## Start all services including agents
	docker compose --profile agents up -d

docker-down:  ## Stop all Docker services
	docker compose down

docker-logs:  ## View dashboard logs
	docker compose logs -f dashboard

docker-prod:  ## Start in production mode with Nginx
	docker compose --profile production up -d

# ── Utils ─────────────────────────────────────────────────────────────────────
clean:  ## Clean Python cache files
	find . -type f -name "*.pyc" -delete
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	rm -rf htmlcov/ .coverage

logs:  ## Tail application logs
	tail -f logs/*.log 2>/dev/null || journalctl -fu arthaai-dashboard

db-reset:  ## Reset the trading database (CAUTION: deletes all trade history)
	@read -p "This will delete all trade history. Type YES to confirm: " ans && [ "$$ans" = "YES" ]
	rm -f arthaai.db
	python -c "from data.database import init_db; init_db(); print('Database reset.')"
