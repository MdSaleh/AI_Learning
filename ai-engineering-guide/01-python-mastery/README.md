# 🐍 Python Mastery for AI Engineering
> From "knows basic Python" to "writes production AI systems"

---

## Module 1: Python Patterns You MUST Know for AI

### 1.1 Type Hints (Non-Negotiable in 2024+)

```python
# ❌ Bad — no type hints
def process_documents(docs, chunk_size, overlap):
    return []

# ✅ Good — fully typed
from typing import Optional, Union, Any
from pathlib import Path

def process_documents(
    docs: list[str],
    chunk_size: int = 500,
    overlap: int = 50,
    output_path: Optional[Path] = None
) -> list[dict[str, Any]]:
    """
    Process documents into chunks for embedding.
    
    Args:
        docs: List of document strings
        chunk_size: Characters per chunk
        overlap: Character overlap between chunks
        output_path: Optional path to save results
        
    Returns:
        List of chunk dictionaries with metadata
    """
    chunks = []
    for doc_idx, doc in enumerate(docs):
        for i in range(0, len(doc), chunk_size - overlap):
            chunk = doc[i:i + chunk_size]
            if chunk.strip():
                chunks.append({
                    "text": chunk,
                    "doc_idx": doc_idx,
                    "char_start": i,
                    "char_end": i + len(chunk)
                })
    return chunks
```

### 1.2 Pydantic Models (The AI Developer's Best Friend)

```python
from pydantic import BaseModel, Field, validator, model_validator
from typing import Optional, Literal
from datetime import datetime
import uuid

# --- Request/Response Models ---
class ChatMessage(BaseModel):
    role: Literal["user", "assistant", "system"]
    content: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    
    class Config:
        json_encoders = {datetime: lambda v: v.isoformat()}

class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=10000)
    conversation_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    temperature: float = Field(default=0.7, ge=0.0, le=2.0)
    max_tokens: int = Field(default=1000, ge=1, le=8192)
    model: str = Field(default="llama3.1:8b")
    stream: bool = False

    @validator("message")
    def strip_message(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("Message cannot be empty or whitespace only")
        return v
    
class ChatResponse(BaseModel):
    response: str
    conversation_id: str
    model: str
    tokens_used: int
    response_time_ms: float
    
class DocumentChunk(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    text: str
    doc_id: str
    metadata: dict[str, Any] = Field(default_factory=dict)
    embedding: Optional[list[float]] = None
    
    @model_validator(mode="after")
    def validate_text_length(self) -> "DocumentChunk":
        if len(self.text) < 10:
            raise ValueError("Chunk text too short — minimum 10 characters")
        return self

# Usage:
request = ChatRequest(message="Hello AI!", temperature=0.9)
print(request.model_dump_json(indent=2))
print(f"Conversation: {request.conversation_id}")
```

### 1.3 Async/Await — Critical for AI APIs

```python
import asyncio
import httpx
import time
from contextlib import asynccontextmanager

# ─── Basic async pattern ───────────────────────────────────────────────────────
async def fetch_embedding(text: str, model: str = "nomic-embed-text") -> list[float]:
    """Fetch embedding from Ollama async."""
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(
            "http://localhost:11434/api/embeddings",
            json={"model": model, "prompt": text}
        )
        response.raise_for_status()
        return response.json()["embedding"]

# ─── Concurrent requests (HUGE for AI performance) ────────────────────────────
async def embed_batch(texts: list[str]) -> list[list[float]]:
    """Embed multiple texts concurrently — 10x faster than sequential."""
    tasks = [fetch_embedding(text) for text in texts]
    embeddings = await asyncio.gather(*tasks, return_exceptions=True)
    
    results = []
    for i, emb in enumerate(embeddings):
        if isinstance(emb, Exception):
            print(f"Failed to embed text {i}: {emb}")
            results.append([])
        else:
            results.append(emb)
    return results

# ─── Async generators for streaming ───────────────────────────────────────────
async def stream_llm_response(prompt: str):
    """Stream LLM response token by token."""
    async with httpx.AsyncClient(timeout=120.0) as client:
        async with client.stream(
            "POST",
            "http://localhost:11434/api/generate",
            json={"model": "llama3.1:8b", "prompt": prompt, "stream": True}
        ) as response:
            async for line in response.aiter_lines():
                if line:
                    import json
                    data = json.loads(line)
                    if not data.get("done"):
                        yield data.get("response", "")

# Use it:
async def main():
    start = time.time()
    
    # Sequential (slow)
    texts = ["Hello world", "AI is cool", "Python rocks"]
    for text in texts:
        emb = await fetch_embedding(text)
        print(f"Embedded: {len(emb)} dims")
    
    print(f"Sequential: {time.time() - start:.2f}s")
    start = time.time()
    
    # Concurrent (fast!)
    embeddings = await embed_batch(texts)
    print(f"Concurrent: {time.time() - start:.2f}s — {len(embeddings)} embeddings")
    
    # Streaming
    async for token in stream_llm_response("Tell me a joke"):
        print(token, end="", flush=True)

asyncio.run(main())
```

### 1.4 Context Managers — Resource Management

```python
from contextlib import asynccontextmanager, contextmanager
from typing import Generator, AsyncGenerator
import chromadb

# ─── Sync context manager ─────────────────────────────────────────────────────
@contextmanager
def timer(name: str) -> Generator[None, None, None]:
    """Measure execution time of a block."""
    start = time.perf_counter()
    try:
        yield
    finally:
        elapsed = (time.perf_counter() - start) * 1000
        print(f"⏱  {name}: {elapsed:.2f}ms")

# Usage:
with timer("embedding 100 docs"):
    results = embed_many_docs(docs)

# ─── Async context manager ────────────────────────────────────────────────────
@asynccontextmanager
async def get_db_client() -> AsyncGenerator[chromadb.Client, None]:
    """Get a ChromaDB client with proper cleanup."""
    client = chromadb.Client()
    try:
        yield client
    finally:
        # cleanup if needed
        pass

# Usage:
async with get_db_client() as db:
    collection = db.get_collection("documents")
    results = collection.query(query_texts=["find similar docs"])
```

### 1.5 Decorators — DRY Code Patterns

```python
import functools
import time
import logging
from typing import Callable, TypeVar, ParamSpec

P = ParamSpec("P")
T = TypeVar("T")
logger = logging.getLogger(__name__)

# ─── Retry decorator ──────────────────────────────────────────────────────────
def retry(
    max_attempts: int = 3,
    delay: float = 1.0,
    backoff: float = 2.0,
    exceptions: tuple = (Exception,)
):
    """Retry a function on failure with exponential backoff."""
    def decorator(func: Callable[P, T]) -> Callable[P, T]:
        @functools.wraps(func)
        async def async_wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
            last_exception = None
            current_delay = delay
            
            for attempt in range(max_attempts):
                try:
                    return await func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e
                    if attempt < max_attempts - 1:
                        logger.warning(
                            f"Attempt {attempt + 1}/{max_attempts} failed: {e}. "
                            f"Retrying in {current_delay:.1f}s..."
                        )
                        await asyncio.sleep(current_delay)
                        current_delay *= backoff
            
            raise last_exception
        return async_wrapper
    return decorator

# ─── Cache decorator ──────────────────────────────────────────────────────────
def cache_embedding(func: Callable) -> Callable:
    """Simple in-memory cache for embeddings."""
    cache: dict[str, list[float]] = {}
    
    @functools.wraps(func)
    async def wrapper(text: str, **kwargs) -> list[float]:
        cache_key = f"{text[:100]}_{hash(text)}"
        if cache_key not in cache:
            cache[cache_key] = await func(text, **kwargs)
        return cache[cache_key]
    
    wrapper.cache = cache
    wrapper.cache_clear = lambda: cache.clear()
    return wrapper

# ─── Timing decorator ────────────────────────────────────────────────────────
def timed(func: Callable[P, T]) -> Callable[P, T]:
    """Log execution time of any function."""
    @functools.wraps(func)
    async def async_wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
        start = time.perf_counter()
        result = await func(*args, **kwargs)
        elapsed = (time.perf_counter() - start) * 1000
        logger.info(f"{func.__name__} completed in {elapsed:.2f}ms")
        return result
    return async_wrapper

# ─── Use them together ────────────────────────────────────────────────────────
@timed
@retry(max_attempts=3, delay=0.5)
@cache_embedding
async def get_embedding(text: str) -> list[float]:
    """Get embedding with retry, caching, and timing."""
    return await fetch_embedding(text)
```

### 1.6 Data Classes and Named Tuples

```python
from dataclasses import dataclass, field
from typing import NamedTuple

# ─── Dataclass (mutable) ──────────────────────────────────────────────────────
@dataclass
class EmbeddingConfig:
    model: str = "nomic-embed-text"
    dimension: int = 768
    batch_size: int = 32
    normalize: bool = True
    
    def __post_init__(self):
        if self.dimension <= 0:
            raise ValueError("Dimension must be positive")
        if self.batch_size <= 0:
            raise ValueError("Batch size must be positive")

# ─── NamedTuple (immutable, hashable) ────────────────────────────────────────
class SearchResult(NamedTuple):
    document_id: str
    text: str
    score: float
    metadata: dict

# Usage:
config = EmbeddingConfig(model="text-embedding-ada-002", dimension=1536)
result = SearchResult("doc-123", "AI is transforming...", 0.95, {"source": "arxiv"})
print(f"Score: {result.score}")  # Immutable, indexed like a tuple
```

---

## Module 2: File & Path Handling

```python
from pathlib import Path
import json
import yaml
import tomllib  # Python 3.11+

# ─── Pathlib (always use this, never os.path) ──────────────────────────────
BASE_DIR = Path(__file__).parent.parent  # Go up 2 levels
DATA_DIR = BASE_DIR / "data"
MODELS_DIR = BASE_DIR / "models"

# Create dirs
DATA_DIR.mkdir(parents=True, exist_ok=True)

# File operations
config_path = BASE_DIR / "config.json"
if config_path.exists():
    config = json.loads(config_path.read_text(encoding="utf-8"))

# Write files
output = {"status": "ok", "results": [...]}
output_path = DATA_DIR / "results.json"
output_path.write_text(json.dumps(output, indent=2), encoding="utf-8")

# Glob patterns
pdf_files = list(DATA_DIR.glob("**/*.pdf"))  # Recursive
txt_files = list(DATA_DIR.glob("*.txt"))      # Non-recursive

# ─── Config loading ───────────────────────────────────────────────────────────
def load_config(path: Path) -> dict:
    suffix = path.suffix.lower()
    text = path.read_text(encoding="utf-8")
    
    if suffix == ".json":
        return json.loads(text)
    elif suffix in (".yml", ".yaml"):
        return yaml.safe_load(text)
    elif suffix == ".toml":
        return tomllib.loads(text)
    else:
        raise ValueError(f"Unsupported config format: {suffix}")
```

---

## Module 3: Environment Variables & Settings

```python
# settings.py — ALWAYS use this pattern
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field, SecretStr
from functools import lru_cache

class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore"
    )
    
    # App
    app_name: str = "AI Service"
    environment: str = Field(default="development", alias="ENV")
    debug: bool = False
    port: int = 8000
    
    # LLM
    ollama_base_url: str = "http://localhost:11434"
    default_model: str = "llama3.1:8b"
    embedding_model: str = "nomic-embed-text"
    
    # Groq (free API key at console.groq.com)
    groq_api_key: Optional[SecretStr] = None
    
    # Database
    chroma_persist_dir: str = "./data/chroma"
    redis_url: str = "redis://localhost:6379"
    
    # Observability
    otlp_endpoint: str = "http://localhost:4317"
    log_level: str = "INFO"
    
    @property
    def is_production(self) -> bool:
        return self.environment == "production"

@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Cached settings — loads once, reused everywhere."""
    return Settings()

# .env file:
# ENV=development
# OLLAMA_BASE_URL=http://localhost:11434
# DEFAULT_MODEL=llama3.1:8b
# GROQ_API_KEY=gsk_xxxx
```

---

## Module 4: Error Handling (Production-Grade)

```python
from fastapi import HTTPException, status
from typing import NoReturn

# ─── Custom exceptions ────────────────────────────────────────────────────────
class AIServiceError(Exception):
    """Base exception for all AI service errors."""
    def __init__(self, message: str, code: str = "AI_ERROR"):
        self.message = message
        self.code = code
        super().__init__(message)

class ModelNotAvailableError(AIServiceError):
    def __init__(self, model: str):
        super().__init__(f"Model '{model}' is not available", "MODEL_NOT_AVAILABLE")

class EmbeddingError(AIServiceError):
    def __init__(self, reason: str):
        super().__init__(f"Embedding failed: {reason}", "EMBEDDING_FAILED")

class DocumentNotFoundError(AIServiceError):
    def __init__(self, doc_id: str):
        super().__init__(f"Document '{doc_id}' not found", "DOCUMENT_NOT_FOUND")

# ─── Global error handler (in FastAPI) ───────────────────────────────────────
from fastapi import Request
from fastapi.responses import JSONResponse

async def ai_error_handler(request: Request, exc: AIServiceError) -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "error": exc.code,
            "message": exc.message,
            "path": str(request.url)
        }
    )

# ─── Result type pattern (instead of exceptions) ─────────────────────────────
from dataclasses import dataclass
from typing import Generic

@dataclass
class Ok(Generic[T]):
    value: T
    
@dataclass  
class Err(Generic[T]):
    error: str
    detail: Optional[str] = None

Result = Union[Ok[T], Err[T]]

async def safe_embed(text: str) -> Result[list[float]]:
    try:
        embedding = await fetch_embedding(text)
        return Ok(embedding)
    except httpx.TimeoutException:
        return Err("timeout", "Embedding service took too long")
    except Exception as e:
        return Err("unknown", str(e))

# Usage:
result = await safe_embed("Hello world")
match result:
    case Ok(value=emb):
        print(f"Got embedding: {len(emb)} dims")
    case Err(error=err, detail=detail):
        print(f"Error: {err} — {detail}")
```

---

## Module 5: Testing Patterns

```python
# tests/test_embeddings.py
import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, patch, MagicMock

# ─── Fixtures ─────────────────────────────────────────────────────────────────
@pytest.fixture
def sample_texts() -> list[str]:
    return [
        "Machine learning is a subset of AI",
        "Neural networks are inspired by the brain",
        "Python is the language of AI",
    ]

@pytest.fixture  
def mock_embedding() -> list[float]:
    import random
    return [random.random() for _ in range(768)]

@pytest_asyncio.fixture
async def mock_llm_client():
    """Mock the LLM HTTP client."""
    with patch("app.services.llm.httpx.AsyncClient") as mock:
        client = AsyncMock()
        mock.return_value.__aenter__ = AsyncMock(return_value=client)
        mock.return_value.__aexit__ = AsyncMock(return_value=None)
        yield client

# ─── Tests ────────────────────────────────────────────────────────────────────
class TestEmbeddingService:
    @pytest.mark.asyncio
    async def test_embed_single_text(self, mock_llm_client, mock_embedding):
        mock_llm_client.post.return_value.json.return_value = {
            "embedding": mock_embedding
        }
        
        result = await fetch_embedding("test text")
        
        assert len(result) == 768
        assert all(isinstance(v, float) for v in result)
    
    @pytest.mark.asyncio
    async def test_embed_batch_concurrent(self, sample_texts, mock_llm_client, mock_embedding):
        mock_llm_client.post.return_value.json.return_value = {
            "embedding": mock_embedding
        }
        
        results = await embed_batch(sample_texts)
        
        assert len(results) == len(sample_texts)
        assert mock_llm_client.post.call_count == len(sample_texts)
    
    @pytest.mark.asyncio  
    async def test_embed_handles_failure_gracefully(self, mock_llm_client):
        mock_llm_client.post.side_effect = Exception("Connection refused")
        
        results = await embed_batch(["text1", "text2"])
        
        # Should return empty lists for failed items
        assert all(r == [] for r in results)

# Run tests:
# pytest tests/ -v
# pytest tests/ -v --cov=app --cov-report=html
# pytest tests/ -v -k "test_embed"  # Run specific tests
# pytest tests/ -v --tb=short       # Short tracebacks
```

---

## Module 6: Python Performance Tips for AI

```python
import numpy as np
from functools import lru_cache

# ─── Use numpy for vector operations ─────────────────────────────────────────
def cosine_similarity_slow(v1: list[float], v2: list[float]) -> float:
    """❌ Slow — pure Python"""
    dot = sum(a * b for a, b in zip(v1, v2))
    mag1 = sum(a**2 for a in v1) ** 0.5
    mag2 = sum(b**2 for b in v2) ** 0.5
    return dot / (mag1 * mag2)

def cosine_similarity_fast(v1: list[float], v2: list[float]) -> float:
    """✅ Fast — numpy"""
    a = np.array(v1)
    b = np.array(v2)
    return np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b))

# Batch similarity (even faster):
def batch_cosine_similarity(query: list[float], docs: list[list[float]]) -> np.ndarray:
    """Compute similarity between query and ALL docs at once."""
    q = np.array(query)
    d = np.array(docs)  # shape: (n_docs, dim)
    
    # Normalize
    q_norm = q / np.linalg.norm(q)
    d_norm = d / np.linalg.norm(d, axis=1, keepdims=True)
    
    return np.dot(d_norm, q_norm)  # Returns array of similarities

# ─── Generator patterns for large datasets ────────────────────────────────────
def read_large_file_chunks(filepath: Path, chunk_size: int = 1000):
    """Read large file in chunks without loading all into memory."""
    with open(filepath, encoding="utf-8") as f:
        while chunk := f.read(chunk_size):
            yield chunk

def process_documents_streaming(doc_paths: list[Path]):
    """Process docs one at a time — memory efficient."""
    for path in doc_paths:
        for chunk in read_large_file_chunks(path):
            yield {"path": str(path), "text": chunk}

# ─── Profile your code ───────────────────────────────────────────────────────
import cProfile
import pstats
import io

def profile_function(func, *args, **kwargs):
    pr = cProfile.Profile()
    pr.enable()
    result = func(*args, **kwargs)
    pr.disable()
    
    s = io.StringIO()
    ps = pstats.Stats(pr, stream=s).sort_stats("cumulative")
    ps.print_stats(10)  # Top 10 slowest
    print(s.getvalue())
    return result
```

---

## Exercises

1. **Type everything**: Take 3 functions you've written in the past. Add full type hints to them.
2. **Async race**: Write a function that fetches data from 5 URLs concurrently using `asyncio.gather`.
3. **Build a retry decorator**: Create a decorator that retries any async function up to N times with backoff.
4. **Profile it**: Write a function that computes cosine similarity in pure Python vs numpy. Profile both and compare.
5. **Test it**: Write 5 unit tests for any function you've written today.

---

**Next Module**: [AI Fundamentals →](../02-ai-fundamentals/README.md)
