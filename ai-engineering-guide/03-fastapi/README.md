# ⚡ FastAPI — Production APIs for AI Services
> Build async, typed, auto-documented APIs used in real AI systems

---

## Why FastAPI for AI?

| Feature | FastAPI | Flask | Django |
|---------|---------|-------|--------|
| Async native | ✅ | ❌ | Partial |
| Auto docs (Swagger) | ✅ | ❌ | ❌ |
| Type hints + validation | ✅ Pydantic | Manual | Forms |
| Performance | ⚡ Very fast | Medium | Slower |
| Streaming responses | ✅ Native | Complex | Complex |
| WebSockets | ✅ | Plugin | Plugin |
| Perfect for AI | ✅ | Ok | No |

---

## 1. Project Structure (Production Pattern)

```
my-ai-api/
├── app/
│   ├── __init__.py
│   ├── main.py              ← FastAPI app + lifespan
│   ├── core/
│   │   ├── __init__.py
│   │   ├── config.py        ← Settings (pydantic-settings)
│   │   ├── logging.py       ← Structured logging setup
│   │   └── dependencies.py  ← FastAPI Depends() functions
│   ├── api/
│   │   ├── __init__.py
│   │   └── v1/
│   │       ├── __init__.py
│   │       ├── router.py    ← Combine all routers
│   │       ├── chat.py      ← Chat endpoints
│   │       └── documents.py ← Document endpoints
│   ├── models/
│   │   ├── __init__.py
│   │   ├── requests.py      ← Request schemas
│   │   └── responses.py     ← Response schemas
│   ├── services/
│   │   ├── __init__.py
│   │   ├── llm.py           ← LLM service
│   │   └── embeddings.py    ← Embedding service
│   └── middleware/
│       ├── __init__.py
│       └── logging.py       ← Request logging middleware
├── tests/
│   ├── conftest.py
│   ├── test_chat.py
│   └── test_documents.py
├── .vscode/
│   ├── settings.json
│   └── launch.json
├── .env
├── .env.example
├── docker-compose.yml
├── Dockerfile
├── pyproject.toml
└── README.md
```

---

## 2. pyproject.toml — Project Configuration

```toml
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "ai-service"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = [
    "fastapi>=0.111.0",
    "uvicorn[standard]>=0.29.0",
    "pydantic>=2.7.0",
    "pydantic-settings>=2.3.0",
    "httpx>=0.27.0",
    "python-multipart>=0.0.9",   # File uploads
    "structlog>=24.2.0",         # Structured logging
    "redis[asyncio]>=5.0.4",     # Conversation history
    "chromadb>=0.5.0",           # Vector DB
    "sentence-transformers>=3.0", # Embeddings
    "opentelemetry-api>=1.25.0", # Tracing
    "opentelemetry-sdk>=1.25.0",
    "opentelemetry-instrumentation-fastapi>=0.46b0",
    "prometheus-client>=0.20.0", # Metrics
]

[project.optional-dependencies]
dev = [
    "pytest>=8.2.0",
    "pytest-asyncio>=0.23.7",
    "pytest-cov>=5.0.0",
    "httpx>=0.27.0",            # Test client
    "ruff>=0.4.9",
    "mypy>=1.10.0",
]

[tool.ruff]
line-length = 88
target-version = "py311"

[tool.ruff.lint]
select = ["E", "W", "F", "I", "B", "UP"]
ignore = ["E501"]

[tool.mypy]
python_version = "3.11"
strict = true
ignore_missing_imports = true

[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]
```

---

## 3. Main App — Production Boilerplate

```python
# app/main.py
import time
from contextlib import asynccontextmanager
from typing import AsyncGenerator

import structlog
from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse
from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST

from app.api.v1.router import api_router
from app.core.config import get_settings
from app.core.logging import setup_logging
from app.core.telemetry import setup_telemetry

settings = get_settings()
logger = structlog.get_logger()

# ─── Prometheus metrics ───────────────────────────────────────────────────────
REQUEST_COUNT = Counter(
    "http_requests_total",
    "Total HTTP requests",
    ["method", "endpoint", "status_code"]
)
REQUEST_DURATION = Histogram(
    "http_request_duration_seconds",
    "HTTP request duration",
    ["method", "endpoint"]
)

# ─── Lifespan (startup + shutdown) ───────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Setup resources on startup, cleanup on shutdown."""
    # Startup
    setup_logging()
    setup_telemetry()
    
    logger.info(
        "starting_up",
        app=settings.app_name,
        environment=settings.environment,
        version="1.0.0"
    )
    
    # Initialize services (warm up models, check connections)
    from app.services.llm import LLMService
    from app.services.embeddings import EmbeddingService
    
    app.state.llm_service = LLMService()
    app.state.embedding_service = EmbeddingService()
    
    await app.state.llm_service.health_check()
    logger.info("services_ready")
    
    yield  # ← App runs here
    
    # Shutdown
    logger.info("shutting_down")
    # Cleanup resources here

# ─── App creation ─────────────────────────────────────────────────────────────
def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.app_name,
        description="Production AI Service API",
        version="1.0.0",
        docs_url="/docs" if not settings.is_production else None,
        redoc_url="/redoc" if not settings.is_production else None,
        lifespan=lifespan,
    )
    
    # ─── Middleware (order matters — outermost runs first on request) ──────────
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"] if not settings.is_production else ["https://yourdomain.com"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.add_middleware(GZipMiddleware, minimum_size=1000)
    
    # ─── Request logging + metrics middleware ──────────────────────────────────
    @app.middleware("http")
    async def observability_middleware(request: Request, call_next):
        start_time = time.perf_counter()
        
        # Generate request ID
        import uuid
        request_id = str(uuid.uuid4())
        request.state.request_id = request_id
        
        # Bind context to all logs in this request
        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(
            request_id=request_id,
            method=request.method,
            path=request.url.path,
        )
        
        logger.info("request_started")
        
        try:
            response = await call_next(request)
            duration = time.perf_counter() - start_time
            
            # Record metrics
            REQUEST_COUNT.labels(
                method=request.method,
                endpoint=request.url.path,
                status_code=response.status_code
            ).inc()
            REQUEST_DURATION.labels(
                method=request.method,
                endpoint=request.url.path
            ).observe(duration)
            
            logger.info(
                "request_completed",
                status_code=response.status_code,
                duration_ms=round(duration * 1000, 2)
            )
            
            # Add request ID to response headers
            response.headers["X-Request-ID"] = request_id
            return response
            
        except Exception as e:
            duration = time.perf_counter() - start_time
            logger.error("request_failed", error=str(e), duration_ms=round(duration * 1000, 2))
            raise
    
    # ─── Routes ───────────────────────────────────────────────────────────────
    app.include_router(api_router, prefix="/api")
    
    @app.get("/health", tags=["System"])
    async def health_check():
        return {"status": "healthy", "service": settings.app_name}
    
    @app.get("/metrics", tags=["System"])
    async def metrics():
        """Prometheus metrics endpoint."""
        return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)
    
    # ─── Error handlers ───────────────────────────────────────────────────────
    @app.exception_handler(Exception)
    async def global_exception_handler(request: Request, exc: Exception):
        logger.error("unhandled_exception", error=str(exc), exc_info=True)
        return JSONResponse(
            status_code=500,
            content={"error": "internal_server_error", "message": "An unexpected error occurred"}
        )
    
    return app

app = create_app()
```

---

## 4. Dependency Injection — FastAPI Superpowers

```python
# app/core/dependencies.py
from typing import Annotated, AsyncGenerator
from fastapi import Depends, HTTPException, Header, status
import redis.asyncio as redis

from app.core.config import Settings, get_settings
from app.services.llm import LLMService
from app.services.embeddings import EmbeddingService

# ─── Settings dependency ──────────────────────────────────────────────────────
SettingsDep = Annotated[Settings, Depends(get_settings)]

# ─── Redis dependency ──────────────────────────────────────────────────────────
async def get_redis(settings: SettingsDep) -> AsyncGenerator[redis.Redis, None]:
    client = redis.from_url(settings.redis_url, decode_responses=True)
    try:
        yield client
    finally:
        await client.aclose()

RedisDep = Annotated[redis.Redis, Depends(get_redis)]

# ─── LLM service from app state ───────────────────────────────────────────────
from fastapi import Request

def get_llm_service(request: Request) -> LLMService:
    return request.app.state.llm_service

LLMServiceDep = Annotated[LLMService, Depends(get_llm_service)]

def get_embedding_service(request: Request) -> EmbeddingService:
    return request.app.state.embedding_service

EmbeddingServiceDep = Annotated[EmbeddingService, Depends(get_embedding_service)]

# ─── API key auth ─────────────────────────────────────────────────────────────
async def verify_api_key(
    x_api_key: Annotated[str | None, Header()] = None,
    settings: Settings = Depends(get_settings)
) -> str:
    if not settings.api_key:
        return "no-auth"  # Auth disabled
    if x_api_key != settings.api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key"
        )
    return x_api_key

AuthDep = Annotated[str, Depends(verify_api_key)]
```

---

## 5. Streaming Responses — Critical for AI Chat

```python
# app/api/v1/chat.py
import json
from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from typing import AsyncGenerator

router = APIRouter(prefix="/chat", tags=["Chat"])

@router.post("/stream")
async def stream_chat(
    request: ChatRequest,
    llm: LLMServiceDep,
    redis_client: RedisDep,
) -> StreamingResponse:
    """Stream chat response token by token — like ChatGPT."""
    
    async def token_generator() -> AsyncGenerator[str, None]:
        try:
            # Get conversation history
            history = await get_conversation_history(redis_client, request.conversation_id)
            
            # Build messages
            messages = history + [{"role": "user", "content": request.message}]
            
            # Stream from LLM
            full_response = ""
            async for token in llm.stream(messages, temperature=request.temperature):
                full_response += token
                # Server-Sent Events format
                yield f"data: {json.dumps({'token': token, 'done': False})}\n\n"
            
            # Save to history
            await save_to_history(redis_client, request.conversation_id, {
                "role": "user", "content": request.message
            })
            await save_to_history(redis_client, request.conversation_id, {
                "role": "assistant", "content": full_response
            })
            
            # Send completion event
            yield f"data: {json.dumps({'token': '', 'done': True, 'conversation_id': request.conversation_id})}\n\n"
            yield "data: [DONE]\n\n"
            
        except Exception as e:
            yield f"data: {json.dumps({'error': str(e)})}\n\n"
    
    return StreamingResponse(
        token_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # Disable nginx buffering
        }
    )

# JavaScript client to consume SSE:
"""
const response = await fetch('/api/v1/chat/stream', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({ message: 'Hello AI!', stream: true })
});

const reader = response.body.getReader();
const decoder = new TextDecoder();

while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    
    const lines = decoder.decode(value).split('\n');
    for (const line of lines) {
        if (line.startsWith('data: ') && line !== 'data: [DONE]') {
            const data = JSON.parse(line.slice(6));
            process.stdout.write(data.token);
        }
    }
}
"""
```

---

## 6. File Upload Endpoints

```python
# app/api/v1/documents.py
from fastapi import APIRouter, UploadFile, File, BackgroundTasks
from pathlib import Path
import shutil
import uuid

router = APIRouter(prefix="/documents", tags=["Documents"])

UPLOAD_DIR = Path("./uploads")
UPLOAD_DIR.mkdir(exist_ok=True)

ALLOWED_TYPES = {"application/pdf", "text/plain", "text/markdown"}
MAX_FILE_SIZE = 50 * 1024 * 1024  # 50MB

@router.post("/upload")
async def upload_document(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    embedding_service: EmbeddingServiceDep = None,
) -> dict:
    """Upload a document and ingest it into the vector store."""
    
    # Validate
    if file.content_type not in ALLOWED_TYPES:
        raise HTTPException(400, f"File type {file.content_type} not allowed")
    
    # Read and check size
    content = await file.read()
    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(413, "File too large (max 50MB)")
    
    # Save file
    doc_id = str(uuid.uuid4())
    ext = Path(file.filename).suffix
    saved_path = UPLOAD_DIR / f"{doc_id}{ext}"
    saved_path.write_bytes(content)
    
    # Queue background ingestion (don't block the response)
    background_tasks.add_task(
        ingest_document_background,
        doc_id=doc_id,
        filepath=saved_path,
        filename=file.filename,
        embedding_service=embedding_service
    )
    
    return {
        "doc_id": doc_id,
        "filename": file.filename,
        "size_bytes": len(content),
        "status": "ingesting",
        "message": "Document is being processed in the background"
    }

async def ingest_document_background(
    doc_id: str,
    filepath: Path,
    filename: str,
    embedding_service: EmbeddingService
) -> None:
    """Background task to ingest document into vector store."""
    logger.info("ingesting_document", doc_id=doc_id, filename=filename)
    try:
        await embedding_service.ingest_file(doc_id, filepath)
        logger.info("document_ingested", doc_id=doc_id)
    except Exception as e:
        logger.error("ingestion_failed", doc_id=doc_id, error=str(e))
```

---

## 7. Testing FastAPI

```python
# tests/conftest.py
import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app

@pytest.fixture
async def client():
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test"
    ) as c:
        yield c

# tests/test_chat.py
async def test_health_check(client):
    response = await client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "healthy"

async def test_chat_endpoint(client):
    response = await client.post(
        "/api/v1/chat",
        json={"message": "Hello!", "temperature": 0.7}
    )
    assert response.status_code == 200
    data = response.json()
    assert "response" in data
    assert "conversation_id" in data

async def test_chat_validates_empty_message(client):
    response = await client.post(
        "/api/v1/chat",
        json={"message": ""}
    )
    assert response.status_code == 422  # Validation error

# Run:
# pytest tests/ -v
# pytest tests/ -v --cov=app --cov-report=term-missing
```

---

## 8. Docker Setup

```dockerfile
# Dockerfile
FROM python:3.11-slim

WORKDIR /app

# Install uv for fast package installation
RUN pip install uv

# Copy dependency files first (layer caching)
COPY pyproject.toml .

# Install dependencies
RUN uv pip install --system -e ".[dev]"

# Copy application code
COPY app/ ./app/
COPY tests/ ./tests/

# Non-root user for security
RUN useradd -m appuser && chown -R appuser:appuser /app
USER appuser

# Health check
HEALTHCHECK --interval=30s --timeout=10s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
```

```yaml
# docker-compose.yml
version: "3.9"
services:
  api:
    build: .
    ports:
      - "8000:8000"
    environment:
      - ENV=development
      - REDIS_URL=redis://redis:6379
      - OLLAMA_BASE_URL=http://host.docker.internal:11434
    volumes:
      - ./data:/app/data
    depends_on:
      - redis
    restart: unless-stopped

  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"
    volumes:
      - redis_data:/data
    command: redis-server --appendonly yes

  prometheus:
    image: prom/prometheus:latest
    ports:
      - "9090:9090"
    volumes:
      - ./observability/prometheus.yml:/etc/prometheus/prometheus.yml

  grafana:
    image: grafana/grafana:latest
    ports:
      - "3000:3000"
    environment:
      - GF_SECURITY_ADMIN_PASSWORD=admin
    volumes:
      - grafana_data:/var/lib/grafana

volumes:
  redis_data:
  grafana_data:
```

---

## Quick Reference: FastAPI Commands

```bash
# Run development server
uvicorn app.main:app --reload --port 8000

# Run with multiple workers (production)
uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4

# Run with gunicorn (production)
gunicorn app.main:app -w 4 -k uvicorn.workers.UvicornWorker

# View auto-generated docs
open http://localhost:8000/docs      # Swagger UI
open http://localhost:8000/redoc     # ReDoc

# Test with curl
curl http://localhost:8000/health
curl -X POST http://localhost:8000/api/v1/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "Hello AI!"}'

# Docker commands
docker compose up -d              # Start all services
docker compose logs -f api        # Follow API logs
docker compose exec api bash      # Shell into container
docker compose down               # Stop all
docker compose down -v            # Stop + remove volumes
```
