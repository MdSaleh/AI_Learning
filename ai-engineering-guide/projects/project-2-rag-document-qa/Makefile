.PHONY: help install dev test lint format clean docker-up

help:
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-18s\033[0m %s\n", $$1, $$2}'

install: ## Install dependencies
	pip install uv && uv pip install --system -e ".[dev]"

dev: ## Start dev server on port 8001
	uvicorn app.main:app --reload --port 8001

test: ## Run tests
	pytest tests/ -v --cov=app --cov-report=term-missing

lint: ## Lint code
	ruff check app/ tests/ --fix && ruff format app/ tests/

docker-up: ## Start services
	docker compose up -d --build

docker-down: ## Stop services
	docker compose down

upload-sample: ## Upload a sample text file
	echo "Machine learning is a subset of AI. It enables computers to learn from data." > /tmp/sample.txt
	curl -X POST http://localhost:8001/documents/upload \
		-F "file=@/tmp/sample.txt"

ask-sample: ## Ask a sample question
	curl -s -X POST http://localhost:8001/ask \
		-H "Content-Type: application/json" \
		-d '{"question": "What is machine learning?"}' | python3 -m json.tool

list-docs: ## List ingested documents
	curl -s http://localhost:8001/documents | python3 -m json.tool

clean:
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	rm -rf .coverage coverage.xml htmlcov/ .pytest_cache/ data/chroma/ uploads/
