.PHONY: help install dev test lint format clean docker-up docker-down docker-logs

help: ## Show available commands
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-18s\033[0m %s\n", $$1, $$2}'

install: ## Install dependencies
	pip install uv && uv pip install --system -e ".[dev]"

dev: ## Start development server with hot reload
	uvicorn app.main:app --reload --port 8000

test: ## Run full test suite with coverage
	pytest tests/ -v --cov=app --cov-report=term-missing --tb=short

test-fast: ## Run tests, stop on first failure
	pytest tests/ -v -x --tb=short

lint: ## Lint and auto-fix code
	ruff check app/ tests/ --fix

format: ## Format code
	ruff format app/ tests/

type-check: ## Static type checking
	mypy app/ --ignore-missing-imports

quality: lint format type-check ## Run all quality checks

docker-up: ## Start all services (API + Redis + Prometheus + Grafana)
	docker compose up -d --build

docker-down: ## Stop all services
	docker compose down

docker-logs: ## Follow API logs
	docker compose logs -f api

docker-shell: ## Open shell in running API container
	docker compose exec api bash

clean: ## Clean generated files
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -name "*.pyc" -delete 2>/dev/null || true
	rm -rf .coverage coverage.xml htmlcov/ .pytest_cache/ .ruff_cache/ dist/ build/

ollama-setup: ## Pull required Ollama models
	ollama pull llama3.1:8b
	ollama pull nomic-embed-text

run-example: ## Send a test chat request
	curl -s -X POST http://localhost:8000/api/v1/chat \
		-H "Content-Type: application/json" \
		-d '{"message": "Explain machine learning in one sentence"}' | python3 -m json.tool
