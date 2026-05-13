# 💡 Tips, Tricks & Common Pitfalls
> Hard-won lessons from production AI systems

---

## LLM Tips

### 1. Always set a timeout — LLMs can hang forever
```python
# ❌ Never do this
async with httpx.AsyncClient() as client:  # No timeout!
    response = await client.post(...)

# ✅ Always do this
async with httpx.AsyncClient(timeout=120.0) as client:
    response = await client.post(...)
```

### 2. Temperature 0 for facts, higher for creativity
```python
# Factual Q&A (RAG, data extraction) → temperature=0.0 or 0.1
# Chat assistant → temperature=0.7
# Creative writing → temperature=1.0-1.2
# Never use > 1.5 in production
```

### 3. Prompt engineering order matters
```
System prompt → Task → Context → Examples → Constraints → Question
```

### 4. Chunk size matters for RAG quality
```python
# Too small (< 100 chars) → loses context, bad answers
# Too large (> 1000 chars) → noisy retrieval, dilutes relevance
# Sweet spot: 400-600 chars with 50-100 char overlap
```

### 5. Always filter by similarity score — don't use garbage chunks
```python
chunks = retrieve(query, top_k=5)
# Filter out low-quality chunks
good_chunks = [c for c in chunks if c["similarity"] > 0.65]
if not good_chunks:
    return "I don't have relevant info for that question."
```

---

## FastAPI Tips

### 6. Use BackgroundTasks for slow operations
```python
# ❌ Blocks the response — user waits 30s for PDF processing
@app.post("/upload")
async def upload(file: UploadFile):
    await process_pdf(file)  # Slow!
    return {"status": "done"}

# ✅ Return immediately, process in background
@app.post("/upload")
async def upload(file: UploadFile, bg: BackgroundTasks):
    bg.add_task(process_pdf, file)  # Async, non-blocking
    return {"status": "processing"}
```

### 7. Never use sync functions in async routes
```python
# ❌ Blocks the entire event loop!
@app.get("/data")
async def get_data():
    time.sleep(5)           # Blocks ALL other requests!
    requests.get("http://...") # sync HTTP — blocks!

# ✅ Use async equivalents
@app.get("/data")
async def get_data():
    await asyncio.sleep(5)           # Non-blocking
    async with httpx.AsyncClient() as client:
        await client.get("http://...") # Async HTTP
```

### 8. Normalize Prometheus label cardinality
```python
# ❌ Creates a new metric series for every user ID — OOM killer
REQUEST_COUNT.labels(user_id=user_id, path=path).inc()

# ✅ Use stable labels only
path_normalized = re.sub(r"/[0-9a-f-]{8,}", "/{id}", path)
REQUEST_COUNT.labels(method=method, path=path_normalized).inc()
```

---

## Docker Tips

### 9. Always use .dockerignore
```
# Without .dockerignore: copies .venv (500MB!) into image
# With .dockerignore: fast builds, small images
echo ".venv/\n__pycache__/\n*.pyc\n.git/\ndata/" > .dockerignore
```

### 10. Layer caching — put slow steps first
```dockerfile
# ✅ Dependencies change rarely → cache them
COPY pyproject.toml .
RUN pip install -e .

# Code changes often → copy last
COPY app/ ./app/
```

---

## Performance Tips

### 11. Batch embeddings — never embed one at a time in loops
```python
# ❌ N sequential HTTP calls = N * latency
for text in texts:
    embedding = await get_embedding(text)  # Sequential!

# ✅ N concurrent calls = ~1 * max_latency
embeddings = await asyncio.gather(*[get_embedding(t) for t in texts])
```

### 12. Cache embeddings for repeated queries
```python
from functools import lru_cache
import hashlib

_embedding_cache: dict[str, list[float]] = {}

async def get_embedding_cached(text: str) -> list[float]:
    key = hashlib.md5(text.encode()).hexdigest()
    if key not in _embedding_cache:
        _embedding_cache[key] = await get_embedding(text)
    return _embedding_cache[key]
```

### 13. Use connection pooling for Redis
```python
# ❌ Creates new connection on every request
async def get_redis():
    client = redis.from_url(url)
    yield client
    await client.aclose()  # Closes connection

# ✅ Use a connection pool (reuses connections)
redis_pool = redis.ConnectionPool.from_url(url, max_connections=10)
async def get_redis():
    client = redis.Redis(connection_pool=redis_pool)
    yield client
```

---

## Debugging Tips

### 14. Add rich logging at every boundary
```python
# Log at: request in → service call → external API → response out
logger.info("chat_started", conversation_id=conv_id)
logger.info("llm_called", model=model, prompt_tokens=tokens)
logger.info("llm_responded", latency_ms=ms, completion_tokens=tokens)
logger.info("chat_complete", total_tokens=total)
```

### 15. Test your streaming with curl -N
```bash
# -N disables buffering so you see tokens as they arrive
curl -N -X POST http://localhost:8000/api/v1/chat/stream \
  -H "Content-Type: application/json" \
  -d '{"message": "Count to 10 slowly"}'
```

### 16. Use httpx directly to debug LLM calls
```python
# Add this anywhere to see exactly what's sent to Ollama
import httpx
import json

async def debug_llm_call(messages):
    payload = {"model": "llama3.1:8b", "messages": messages}
    print("Sending to Ollama:")
    print(json.dumps(payload, indent=2))

    async with httpx.AsyncClient(timeout=120) as client:
        r = await client.post("http://localhost:11434/api/chat", json=payload)
        print("Response:")
        print(json.dumps(r.json(), indent=2))
```

---

## Security Tips

### 17. Never log sensitive data
```python
# ❌ Logs API keys, passwords, PII
logger.info("request", headers=dict(request.headers), body=body)

# ✅ Log only safe fields
logger.info("request", path=request.url.path, method=request.method)
```

### 18. Validate file uploads strictly
```python
ALLOWED_TYPES = {"application/pdf", "text/plain"}
MAX_SIZE = 50 * 1024 * 1024  # 50MB

content = await file.read()
if file.content_type not in ALLOWED_TYPES:
    raise HTTPException(415, "File type not allowed")
if len(content) > MAX_SIZE:
    raise HTTPException(413, "File too large")

# Also check magic bytes (don't trust content_type alone!)
if content[:4] == b"%PDF":
    # It's actually a PDF
    pass
```

### 19. Rate limit your AI endpoints
```python
# pip install slowapi
from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter

@app.post("/api/v1/chat")
@limiter.limit("10/minute")  # Max 10 requests/minute per IP
async def chat(request: Request, body: ChatRequest):
    ...
```

---

## Common Mistakes & Fixes

| Mistake | Fix |
|---------|-----|
| Ollama not responding | Run `ollama serve` in separate terminal |
| ChromaDB "no documents found" | Check ingestion completed; add `time.sleep(1)` in tests |
| Streaming not working in browser | Set `X-Accel-Buffering: no` header; disable nginx buffering |
| Tests fail with "Redis connection refused" | Add Redis service to docker compose or use mock |
| Pydantic v2 error | Update `from pydantic import validator` → `field_validator` |
| Slow embeddings | Use batch embedding with `asyncio.gather` |
| OOM error in Docker | Increase Docker memory limit; use smaller model |
| Port already in use | `lsof -i :8000` then `kill -9 <PID>` |
| GitHub Actions pip cache miss | Add `cache: "pip"` to `setup-python` action |
