.PHONY: help install dev test lint docker-up run-agent list-tools

help:
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-18s\033[0m %s\n", $$1, $$2}'

install: ## Install dependencies
	pip install uv && uv pip install --system -e ".[dev]"

dev: ## Start dev server on port 8002
	uvicorn app.main:app --reload --port 8002

test: ## Run tests
	pytest tests/ -v --cov=app --cov-report=term-missing

lint: ## Lint and format
	ruff check app/ tests/ --fix && ruff format app/ tests/

docker-up: ## Start services
	docker compose up -d --build

docker-down: ## Stop services
	docker compose down

list-tools: ## List available agent tools
	curl -s http://localhost:8002/tools | python3 -m json.tool

run-agent: ## Run agent with sample query
	curl -s -X POST http://localhost:8002/agent/run \
		-H "Content-Type: application/json" \
		-d '{"query": "What is 2 to the power of 32? Also what time is it now?"}' | python3 -m json.tool

test-calculator: ## Test calculator tool directly
	curl -s -X POST http://localhost:8002/tools/calculator \
		-H "Content-Type: application/json" \
		-d '{"expression": "sqrt(144) * pi"}' | python3 -m json.tool

test-python: ## Test Python runner tool
	curl -s -X POST http://localhost:8002/tools/run_python \
		-H "Content-Type: application/json" \
		-d '{"code": "print([i**2 for i in range(10)])"}' | python3 -m json.tool

clean:
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	rm -rf .coverage coverage.xml htmlcov/ .pytest_cache/
