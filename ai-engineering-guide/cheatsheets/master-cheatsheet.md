# 📋 The Ultimate AI Engineering Cheatsheet
> Every command you'll use daily — bookmark this page

---

## 🐍 Python / UV

```bash
# Environment
python3.11 -m venv .venv          # Create venv
source .venv/bin/activate          # Activate (Linux/Mac)
.venv\Scripts\activate             # Activate (Windows)
deactivate                         # Exit venv

# UV (fast pip)
pip install uv                     # Install UV
uv pip install fastapi             # Install package
uv pip install -e ".[dev]"        # Install with dev extras
uv pip install -r requirements.txt # From requirements file
uv pip freeze > requirements.txt   # Export requirements

# Debugging
python -m pdb script.py           # Run with debugger
python -c "import module; help(module)" # Quick help
python -m py_compile file.py      # Syntax check only
python -m cProfile -s cumulative script.py # Profile performance
```

---

## ⚡ FastAPI / Uvicorn

```bash
# Development
uvicorn app.main:app --reload --port 8000       # Hot reload
uvicorn app.main:app --reload --log-level debug  # Debug logs

# Production
uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4
gunicorn app.main:app -w 4 -k uvicorn.workers.UvicornWorker

# Test API
curl http://localhost:8000/health
curl http://localhost:8000/docs   # Swagger UI (browser)

curl -X POST http://localhost:8000/api/v1/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "Hello AI!"}'

# Stream response
curl -N http://localhost:8000/api/v1/chat/stream \
  -X POST \
  -H "Content-Type: application/json" \
  -d '{"message": "Tell me a story", "stream": true}'
```

---

## 🦙 Ollama

```bash
# Setup
curl -fsSL https://ollama.ai/install.sh | sh  # Install
ollama serve                                    # Start server
ollama list                                     # List models
ollama ps                                       # Running models

# Models
ollama pull llama3.1:8b       # Pull model
ollama pull nomic-embed-text  # Pull embedding model
ollama run llama3.1:8b        # Interactive chat
ollama rm llama3.1:8b         # Remove model

# API test
curl http://localhost:11434/api/generate \
  -d '{"model":"llama3.1:8b","prompt":"Hi","stream":false}'

curl http://localhost:11434/api/embeddings \
  -d '{"model":"nomic-embed-text","prompt":"Hello world"}'
```

---

## 🐳 Docker

```bash
# Build
docker build -t myapp:latest .              # Build image
docker build -t myapp:latest --no-cache .   # Force rebuild

# Run
docker run -p 8000:8000 myapp:latest        # Run container
docker run -d --name myapp -p 8000:8000 myapp:latest  # Background
docker run --rm -it myapp:latest bash       # Interactive shell

# Compose
docker compose up -d          # Start all services (background)
docker compose up --build -d  # Rebuild then start
docker compose down           # Stop all
docker compose down -v        # Stop + delete volumes
docker compose logs -f api    # Follow logs for 'api' service
docker compose logs --tail=50 # Last 50 lines
docker compose exec api bash  # Shell inside container
docker compose ps             # Service status
docker compose restart api    # Restart one service

# Inspect
docker ps                     # Running containers
docker ps -a                  # All containers (including stopped)
docker images                 # List images
docker stats                  # Live resource usage
docker logs myapp -f          # Follow container logs
docker inspect myapp          # Full container info

# Cleanup
docker rm $(docker ps -aq)    # Remove all stopped containers
docker rmi $(docker images -q) # Remove all images
docker system prune -a        # Nuclear option — remove everything
docker volume prune           # Remove unused volumes
```

---

## 📦 Git

```bash
# Setup
git init                          # New repo
git clone URL                     # Clone
git remote add origin URL         # Add remote

# Daily workflow
git status                        # What changed?
git diff                          # See changes
git add .                         # Stage all
git add -p                        # Stage interactively (review hunks)
git commit -m "feat: add chat endpoint"
git push origin main

# Branches
git checkout -b feature/add-rag   # Create + switch
git switch main                   # Switch branch (modern)
git merge feature/add-rag         # Merge
git branch -d feature/add-rag     # Delete branch

# History
git log --oneline --graph --all   # Visual log
git log -5 --stat                 # Last 5 commits with file changes
git show HEAD                     # Show last commit

# Undo
git restore file.py               # Discard unstaged changes
git restore --staged file.py      # Unstage
git reset HEAD~1                  # Undo last commit (keep changes)
git reset --hard HEAD~1           # Undo last commit (LOSE changes)
git revert HEAD                   # Undo commit with new commit (safe for shared)

# Stash
git stash                         # Save dirty work
git stash pop                     # Restore stashed work
git stash list                    # List stashes

# Useful
git diff main...HEAD              # Changes vs main
git cherry-pick abc123            # Apply specific commit
git blame file.py                 # Who changed each line?
```

---

## 🧪 Pytest

```bash
# Run tests
pytest                              # Run all
pytest tests/ -v                   # Verbose
pytest tests/ -v -s                # Show print() output
pytest tests/ -x                   # Stop on first failure
pytest tests/test_chat.py -v       # Specific file
pytest tests/ -k "test_chat"       # Tests matching pattern
pytest tests/ -k "not slow"        # Exclude pattern
pytest tests/ --tb=short           # Short tracebacks
pytest tests/ --tb=line            # One-line tracebacks

# Coverage
pytest tests/ --cov=app --cov-report=term-missing   # Terminal report
pytest tests/ --cov=app --cov-report=html            # HTML report (open htmlcov/index.html)
pytest tests/ --cov=app --cov-fail-under=80          # Fail if < 80% coverage

# Marks
pytest tests/ -m asyncio           # Only async tests
pytest tests/ -m "not integration" # Skip integration tests

# Debug specific test
pytest tests/test_chat.py::TestChat::test_chat_returns_200 -v -s
```

---

## 📊 Prometheus Queries

```promql
# Request metrics
rate(http_requests_total[5m])                            # Req/sec
rate(http_requests_total{status_code=~"5.."}[5m])        # Error rate
increase(http_requests_total[1h])                        # Total in 1 hour

# Latency
histogram_quantile(0.50, rate(http_request_duration_seconds_bucket[5m]))  # P50
histogram_quantile(0.95, rate(http_request_duration_seconds_bucket[5m]))  # P95
histogram_quantile(0.99, rate(http_request_duration_seconds_bucket[5m]))  # P99

# LLM specific
rate(llm_requests_total{status="error"}[5m])             # LLM errors/sec
rate(llm_tokens_total[1h]) by (model)                    # Tokens/hr by model
histogram_quantile(0.95, rate(llm_latency_seconds_bucket[5m]))  # LLM P95 latency

# Alerts (add to prometheus alerts.yml)
# Alert if error rate > 5%:
# rate(http_requests_total{status_code=~"5.."}[5m]) / rate(http_requests_total[5m]) > 0.05
```

---

## ☁️ AWS CLI

```bash
# Configure
aws configure                    # Set access key, secret, region

# EC2
aws ec2 describe-instances       # List instances
aws ec2 start-instances --instance-ids i-xxx  # Start
aws ec2 stop-instances --instance-ids i-xxx   # Stop

# ECR (Docker registry)
aws ecr get-login-password --region us-east-1 | \
  docker login --username AWS --password-stdin \
  ACCOUNT.dkr.ecr.us-east-1.amazonaws.com

aws ecr create-repository --repository-name my-app

# Lambda
aws lambda list-functions                    # List functions
aws lambda invoke --function-name my-fn \
  --payload '{"key":"value"}' response.json  # Invoke
aws lambda update-function-code \
  --function-name my-fn \
  --zip-file fileb://lambda.zip              # Update code

# S3
aws s3 ls                        # List buckets
aws s3 cp file.txt s3://bucket/  # Upload
aws s3 sync ./data s3://bucket/  # Sync directory
aws s3 presign s3://bucket/file  # Generate signed URL

# CloudWatch Logs
aws logs tail /aws/lambda/my-fn --follow  # Stream logs
aws logs get-log-events \
  --log-group-name /aws/lambda/my-fn \
  --log-stream-name "latest"              # Get events
```

---

## 🔧 VS Code Keyboard Shortcuts

| Action | Windows/Linux | Mac |
|--------|--------------|-----|
| Command Palette | `Ctrl+Shift+P` | `Cmd+Shift+P` |
| Quick Open | `Ctrl+P` | `Cmd+P` |
| Terminal | `Ctrl+\`` | `Cmd+\`` |
| Find in Files | `Ctrl+Shift+F` | `Cmd+Shift+F` |
| Go to Definition | `F12` | `F12` |
| Peek Definition | `Alt+F12` | `Option+F12` |
| Rename Symbol | `F2` | `F2` |
| Set Breakpoint | `F9` | `F9` |
| Start Debug | `F5` | `F5` |
| Step Over | `F10` | `F10` |
| Step Into | `F11` | `F11` |
| Format Document | `Shift+Alt+F` | `Shift+Option+F` |
| Multi-cursor | `Alt+Click` | `Option+Click` |
| Select All Occurrences | `Ctrl+Shift+L` | `Cmd+Shift+L` |
| Comment Line | `Ctrl+/` | `Cmd+/` |
| Duplicate Line | `Shift+Alt+↓` | `Shift+Option+↓` |
| Move Line | `Alt+↑/↓` | `Option+↑/↓` |

---

## 🏃 Quick Reference: Start a New AI Project

```bash
# 1. Create project
mkdir my-ai-project && cd my-ai-project
git init
python3.11 -m venv .venv && source .venv/bin/activate

# 2. Create structure
mkdir -p app/{api/v1,core,models,services} tests .vscode

# 3. Install deps
pip install uv
uv pip install fastapi uvicorn pydantic pydantic-settings httpx structlog \
  prometheus-client redis chromadb pytest pytest-asyncio ruff

# 4. Create pyproject.toml, .env, .gitignore
# (copy from this guide's project templates)

# 5. Start Ollama
ollama serve &
ollama pull llama3.1:8b

# 6. Run and test
uvicorn app.main:app --reload
curl http://localhost:8000/health

# 7. First commit
git add . && git commit -m "feat: initial project setup"
git remote add origin git@github.com:YOU/my-ai-project.git
git push -u origin main
```
