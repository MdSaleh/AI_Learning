# 🔄 CI/CD for AI Services — GitHub Actions
> Automate testing, quality checks, and deployment — all free

---

## 1. Complete CI Pipeline

```yaml
# .github/workflows/ci.yml
name: CI Pipeline

on:
  push:
    branches: [main, develop]
  pull_request:
    branches: [main]

env:
  PYTHON_VERSION: "3.11"
  
jobs:
  # ─── Job 1: Code Quality ────────────────────────────────────────────────────
  quality:
    name: Code Quality
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      
      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: ${{ env.PYTHON_VERSION }}
          cache: "pip"
      
      - name: Install uv
        run: pip install uv
      
      - name: Install dependencies
        run: uv pip install --system -e ".[dev]"
      
      - name: Run Ruff linter
        run: ruff check app/ tests/ --output-format=github
      
      - name: Run Ruff formatter check
        run: ruff format app/ tests/ --check
      
      - name: Run MyPy type checking
        run: mypy app/ --ignore-missing-imports

  # ─── Job 2: Tests ──────────────────────────────────────────────────────────
  test:
    name: Tests
    runs-on: ubuntu-latest
    needs: quality
    
    services:
      redis:
        image: redis:7-alpine
        ports: ["6379:6379"]
        options: >-
          --health-cmd "redis-cli ping"
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5
    
    steps:
      - uses: actions/checkout@v4
      
      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: ${{ env.PYTHON_VERSION }}
          cache: "pip"
      
      - name: Install dependencies
        run: |
          pip install uv
          uv pip install --system -e ".[dev]"
      
      - name: Run tests with coverage
        env:
          REDIS_URL: redis://localhost:6379
          ENV: test
          # Mock LLM — don't need real Ollama in CI
          MOCK_LLM: "true"
        run: |
          pytest tests/ \
            -v \
            --cov=app \
            --cov-report=xml \
            --cov-report=term-missing \
            --tb=short \
            -x  # Stop on first failure
      
      - name: Upload coverage to Codecov (free)
        uses: codecov/codecov-action@v4
        with:
          files: ./coverage.xml
          fail_ci_if_error: false

  # ─── Job 3: Security Scan ───────────────────────────────────────────────────
  security:
    name: Security Scan
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      
      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: ${{ env.PYTHON_VERSION }}
      
      - name: Install bandit
        run: pip install bandit[toml] safety
      
      - name: Run Bandit security scan
        run: bandit -r app/ -ll  # Only medium and high severity
      
      - name: Check for known vulnerabilities
        run: safety check --full-report

  # ─── Job 4: Docker Build ────────────────────────────────────────────────────
  docker:
    name: Docker Build
    runs-on: ubuntu-latest
    needs: [quality, test]
    steps:
      - uses: actions/checkout@v4
      
      - name: Set up Docker Buildx
        uses: docker/setup-buildx-action@v3
      
      - name: Build Docker image
        uses: docker/build-push-action@v5
        with:
          context: .
          push: false  # Just build, don't push (no registry needed in CI)
          tags: ai-service:${{ github.sha }}
          cache-from: type=gha
          cache-to: type=gha,mode=max
      
      - name: Test Docker image starts correctly
        run: |
          docker run -d \
            --name test-container \
            -p 8000:8000 \
            -e ENV=test \
            -e MOCK_LLM=true \
            ai-service:${{ github.sha }}
          
          # Wait for health check
          sleep 10
          curl -f http://localhost:8000/health || exit 1
          docker rm -f test-container
```

---

## 2. CD Pipeline — Deploy to AWS

```yaml
# .github/workflows/deploy.yml
name: Deploy to AWS

on:
  push:
    branches: [main]
    tags: ["v*"]  # Deploy on version tags too

jobs:
  deploy:
    name: Deploy to ECS
    runs-on: ubuntu-latest
    environment: production  # Requires manual approval
    
    steps:
      - uses: actions/checkout@v4
      
      - name: Configure AWS credentials
        uses: aws-actions/configure-aws-credentials@v4
        with:
          aws-access-key-id: ${{ secrets.AWS_ACCESS_KEY_ID }}
          aws-secret-access-key: ${{ secrets.AWS_SECRET_ACCESS_KEY }}
          aws-region: us-east-1
      
      - name: Login to Amazon ECR
        id: login-ecr
        uses: aws-actions/amazon-ecr-login@v2
      
      - name: Build and push to ECR
        id: build-image
        env:
          ECR_REGISTRY: ${{ steps.login-ecr.outputs.registry }}
          ECR_REPOSITORY: ai-service
          IMAGE_TAG: ${{ github.sha }}
        run: |
          docker build -t $ECR_REGISTRY/$ECR_REPOSITORY:$IMAGE_TAG .
          docker push $ECR_REGISTRY/$ECR_REPOSITORY:$IMAGE_TAG
          echo "image=$ECR_REGISTRY/$ECR_REPOSITORY:$IMAGE_TAG" >> $GITHUB_OUTPUT
      
      - name: Update ECS service
        run: |
          aws ecs update-service \
            --cluster ai-service-cluster \
            --service ai-service \
            --force-new-deployment
      
      - name: Wait for deployment to complete
        run: |
          aws ecs wait services-stable \
            --cluster ai-service-cluster \
            --services ai-service
      
      - name: Notify on success
        if: success()
        run: echo "✅ Deployment successful! Image: ${{ steps.build-image.outputs.image }}"
```

---

## 3. PR Quality Checks Workflow

```yaml
# .github/workflows/pr-checks.yml
name: PR Checks

on:
  pull_request:
    types: [opened, synchronize, reopened]

jobs:
  pr-size:
    name: Check PR Size
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0
      
      - name: Check PR size
        run: |
          CHANGES=$(git diff --stat origin/main...HEAD | tail -1)
          echo "Changes: $CHANGES"
          
          LINES=$(git diff origin/main...HEAD | wc -l)
          if [ $LINES -gt 1000 ]; then
            echo "⚠️ Large PR detected ($LINES lines). Consider splitting."
          fi

  commit-messages:
    name: Validate Commit Messages
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0
      
      - name: Check conventional commits
        run: |
          git log origin/main..HEAD --format="%s" | while read msg; do
            if ! echo "$msg" | grep -qE "^(feat|fix|docs|style|refactor|test|chore|ci)(\(.+\))?: .+"; then
              echo "❌ Bad commit message: '$msg'"
              echo "Use: feat: add chat endpoint"
              exit 1
            fi
          done
          echo "✅ All commit messages follow conventional commits"
```

---

## 4. GitHub Repository Setup

```bash
# ─── Secrets to add in GitHub (Settings → Secrets → Actions) ─────────────────
# AWS_ACCESS_KEY_ID
# AWS_SECRET_ACCESS_KEY
# GROQ_API_KEY (if using Groq)

# ─── Branch protection rules (Settings → Branches → main) ────────────────────
# ✅ Require pull request before merging
# ✅ Require status checks: quality, test, security, docker
# ✅ Require branches to be up to date
# ✅ Dismiss stale reviews on push

# ─── .gitignore for Python AI projects ───────────────────────────────────────
cat > .gitignore << 'EOF'
# Python
__pycache__/
*.py[cod]
*.pyo
.venv/
venv/
env/
*.egg-info/
dist/
build/
.eggs/

# Environment
.env
.env.local
.env.*.local

# Data (don't commit large files)
data/
uploads/
*.pdf
*.faiss

# VS Code
.vscode/
!.vscode/settings.json
!.vscode/launch.json

# Testing
.coverage
coverage.xml
htmlcov/
.pytest_cache/

# OS
.DS_Store
Thumbs.db

# Docker
*.log

# ML models (too large for Git)
*.bin
*.safetensors
*.gguf
models/
EOF

# ─── Conventional Commits Quick Reference ─────────────────────────────────────
# feat: new feature
# fix: bug fix
# docs: documentation only
# style: formatting, no logic change
# refactor: code restructure, no feature/fix
# test: add/update tests
# chore: maintenance tasks
# ci: CI/CD changes
# perf: performance improvement

# Examples:
# git commit -m "feat(chat): add streaming response support"
# git commit -m "fix(rag): handle empty query edge case"
# git commit -m "docs: update API documentation"
# git commit -m "ci: add security scan to pipeline"
```

---

## 5. Makefile — Standardize All Commands

```makefile
# Makefile
.PHONY: help install dev test lint format type-check security docker-build docker-up docker-down clean

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

install: ## Install dependencies
	pip install uv
	uv pip install --system -e ".[dev]"

dev: ## Start development server
	uvicorn app.main:app --reload --port 8000

test: ## Run tests
	pytest tests/ -v --cov=app --cov-report=term-missing

test-fast: ## Run tests without coverage
	pytest tests/ -v -x

lint: ## Run linter
	ruff check app/ tests/ --fix

format: ## Format code
	ruff format app/ tests/

type-check: ## Run type checker
	mypy app/

security: ## Run security checks
	bandit -r app/ -ll
	safety check

quality: lint format type-check ## Run all quality checks

docker-build: ## Build Docker image
	docker build -t ai-service:local .

docker-up: ## Start all services
	docker compose up -d

docker-down: ## Stop all services
	docker compose down

docker-logs: ## Follow API logs
	docker compose logs -f api

clean: ## Clean generated files
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -name "*.pyc" -delete
	rm -rf .coverage coverage.xml htmlcov/ .pytest_cache/
```

Usage:
```bash
make help         # See all commands
make install      # Install deps
make dev          # Start dev server
make test         # Run tests
make quality      # All quality checks
make docker-up    # Start everything
```
