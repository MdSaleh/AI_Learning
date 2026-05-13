# 🤖 Project 1: AI Chat API
> Streaming chat API with local LLM, conversation history, and full observability

## What You'll Build
- Streaming chat API (like ChatGPT)
- Multi-turn conversations with Redis memory
- Local LLM via Ollama (completely free)
- Prometheus metrics + structured logging
- Full test suite
- Docker Compose deployment

## Tech Stack
- FastAPI + Uvicorn
- Ollama (Llama 3.1 8B) — local, free
- Redis — conversation history
- Prometheus — metrics
- structlog — logging

## Run It
```bash
# 1. Start Ollama (in a separate terminal)
ollama serve
ollama pull llama3.1:8b

# 2. Start services
docker compose up -d redis

# 3. Install deps
python -m venv .venv && source .venv/bin/activate
pip install uv && uv pip install -e ".[dev]"

# 4. Run API
uvicorn app.main:app --reload

# 5. Test it
curl -X POST http://localhost:8000/api/v1/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "What is machine learning?"}'
```
