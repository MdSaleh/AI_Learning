# 🔭 Observability for AI Services
> OpenTelemetry + Prometheus + Grafana — The Free Observability Stack

---

## The Three Pillars of Observability

```
Logs    → "What happened?" — Structured JSON log entries
Metrics → "How is it performing?" — Numbers over time (latency, error rate, etc.)
Traces  → "Where did time go?" — Request flow across services
```

---

## 1. Structured Logging with structlog

```python
# app/core/logging.py
import logging
import sys
import structlog
from app.core.config import get_settings

def setup_logging() -> None:
    """Configure structlog for production-grade structured logging."""
    settings = get_settings()
    
    # Configure standard library logging
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=getattr(logging, settings.log_level.upper())
    )
    
    # Configure structlog processors
    processors = [
        structlog.contextvars.merge_contextvars,    # Include request context
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
    ]
    
    if settings.environment == "development":
        # Pretty colored output for development
        processors.append(structlog.dev.ConsoleRenderer(colors=True))
    else:
        # JSON output for production (goes to log aggregation)
        processors.extend([
            structlog.processors.dict_tracebacks,
            structlog.processors.JSONRenderer()
        ])
    
    structlog.configure(
        processors=processors,
        wrapper_class=structlog.make_filtering_bound_logger(
            getattr(logging, settings.log_level.upper())
        ),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )

# Usage in any module:
import structlog
logger = structlog.get_logger()

# Log with structured key-value pairs (NOT string formatting!)
logger.info("chat_request_received",
    model="llama3.1:8b",
    conversation_id="abc-123",
    message_length=42,
    temperature=0.7
)

logger.warning("high_latency_detected",
    endpoint="/api/v1/chat",
    duration_ms=4532,
    threshold_ms=3000
)

logger.error("llm_call_failed",
    model="llama3.1:8b",
    error="Connection refused",
    retry_attempt=2,
    exc_info=True  # Includes stack trace
)

# Bind context that appears in ALL subsequent log messages:
structlog.contextvars.bind_contextvars(
    request_id="req-456",
    user_id="user-789"
)
# Now every log in this request includes request_id and user_id automatically
```

---

## 2. Prometheus Metrics

```python
# app/core/metrics.py
from prometheus_client import Counter, Histogram, Gauge, Summary

# ─── Define all metrics centrally ────────────────────────────────────────────

# Counters (only go up)
LLM_REQUESTS_TOTAL = Counter(
    "llm_requests_total",
    "Total LLM API calls",
    ["model", "endpoint", "status"]  # Labels
)

TOKENS_USED_TOTAL = Counter(
    "tokens_used_total",
    "Total tokens consumed",
    ["model", "type"]  # type: prompt | completion
)

DOCUMENTS_INGESTED_TOTAL = Counter(
    "documents_ingested_total",
    "Total documents ingested",
    ["file_type", "status"]
)

# Histograms (track distributions — great for latencies)
LLM_LATENCY_SECONDS = Histogram(
    "llm_latency_seconds",
    "LLM response time in seconds",
    ["model"],
    buckets=[0.1, 0.25, 0.5, 1.0, 2.0, 5.0, 10.0, 30.0]  # Latency buckets
)

EMBEDDING_LATENCY_SECONDS = Histogram(
    "embedding_latency_seconds",
    "Embedding generation time",
    ["model"],
    buckets=[0.01, 0.05, 0.1, 0.25, 0.5, 1.0]
)

RAG_RETRIEVAL_LATENCY_SECONDS = Histogram(
    "rag_retrieval_latency_seconds",
    "RAG document retrieval time",
    buckets=[0.001, 0.01, 0.05, 0.1, 0.5]
)

# Gauges (can go up or down)
VECTOR_DB_DOCUMENT_COUNT = Gauge(
    "vector_db_document_count",
    "Number of documents in vector DB"
)

ACTIVE_CONVERSATIONS = Gauge(
    "active_conversations_total",
    "Currently active conversation sessions"
)

# Summary (percentile calculations)
TOKENS_PER_REQUEST = Summary(
    "tokens_per_request",
    "Tokens per LLM request",
    ["model"]
)

# ─── Helper context manager for timing ───────────────────────────────────────
import time
from contextlib import contextmanager
from typing import Generator

@contextmanager
def track_llm_call(model: str) -> Generator[None, None, None]:
    """Context manager that records LLM call metrics."""
    start = time.perf_counter()
    status = "success"
    try:
        yield
    except Exception:
        status = "error"
        raise
    finally:
        duration = time.perf_counter() - start
        LLM_LATENCY_SECONDS.labels(model=model).observe(duration)
        LLM_REQUESTS_TOTAL.labels(
            model=model,
            endpoint="generate",
            status=status
        ).inc()

# Usage:
async def call_llm_with_metrics(prompt: str, model: str) -> str:
    with track_llm_call(model):
        response = await generate_with_ollama(prompt, model)
    
    # Record tokens (estimate: 4 chars ≈ 1 token)
    prompt_tokens = len(prompt) // 4
    completion_tokens = len(response) // 4
    TOKENS_USED_TOTAL.labels(model=model, type="prompt").inc(prompt_tokens)
    TOKENS_USED_TOTAL.labels(model=model, type="completion").inc(completion_tokens)
    
    return response
```

---

## 3. OpenTelemetry Distributed Tracing

```python
# app/core/telemetry.py
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
from opentelemetry.instrumentation.redis import RedisInstrumentor
from opentelemetry.sdk.resources import Resource

def setup_telemetry() -> None:
    """Configure OpenTelemetry tracing."""
    from app.core.config import get_settings
    settings = get_settings()
    
    # Define service identity
    resource = Resource.create({
        "service.name": settings.app_name,
        "service.version": "1.0.0",
        "deployment.environment": settings.environment,
    })
    
    provider = TracerProvider(resource=resource)
    
    # Export to OTLP collector (Jaeger, Tempo, etc.)
    if settings.otlp_endpoint:
        otlp_exporter = OTLPSpanExporter(endpoint=settings.otlp_endpoint)
        provider.add_span_processor(BatchSpanProcessor(otlp_exporter))
    
    # Also print to console in development
    if settings.environment == "development":
        console_exporter = ConsoleSpanExporter()
        provider.add_span_processor(BatchSpanProcessor(console_exporter))
    
    trace.set_tracer_provider(provider)
    
    # Auto-instrument libraries (magic! 🪄)
    FastAPIInstrumentor.instrument()
    HTTPXClientInstrumentor.instrument()
    RedisInstrumentor.instrument()

# Using traces in your services:
tracer = trace.get_tracer(__name__)

async def rag_pipeline_with_tracing(query: str) -> dict:
    """Full RAG pipeline with distributed tracing."""
    
    # Create a parent span for the whole pipeline
    with tracer.start_as_current_span("rag_pipeline") as span:
        span.set_attribute("query.length", len(query))
        span.set_attribute("query.text", query[:100])  # First 100 chars
        
        # Child span for embedding
        with tracer.start_as_current_span("generate_query_embedding") as embed_span:
            embedding = await get_embedding(query)
            embed_span.set_attribute("embedding.dimensions", len(embedding))
        
        # Child span for retrieval
        with tracer.start_as_current_span("vector_search") as search_span:
            chunks = await retrieve_relevant_chunks(query, collection, top_k=5)
            search_span.set_attribute("chunks.retrieved", len(chunks))
            search_span.set_attribute("chunks.top_score", chunks[0]["similarity"] if chunks else 0)
        
        # Child span for generation
        with tracer.start_as_current_span("llm_generation") as gen_span:
            answer = await generate_answer(query, chunks)
            gen_span.set_attribute("answer.length", len(answer))
        
        span.set_attribute("pipeline.success", True)
        
        return {"answer": answer, "sources": [c["source"] for c in chunks]}
```

---

## 4. Prometheus Configuration

```yaml
# observability/prometheus.yml
global:
  scrape_interval: 15s
  evaluation_interval: 15s

scrape_configs:
  - job_name: "ai-service"
    static_configs:
      - targets: ["api:8000"]
    metrics_path: "/metrics"
    
  - job_name: "prometheus"
    static_configs:
      - targets: ["localhost:9090"]
```

---

## 5. Grafana Dashboard (JSON)

Import this into Grafana (Dashboards → Import):

```json
{
  "title": "AI Service Dashboard",
  "panels": [
    {
      "title": "Request Rate",
      "type": "stat",
      "targets": [{
        "expr": "rate(http_requests_total[5m])",
        "legendFormat": "req/s"
      }]
    },
    {
      "title": "LLM Latency P95",
      "type": "gauge",
      "targets": [{
        "expr": "histogram_quantile(0.95, rate(llm_latency_seconds_bucket[5m]))",
        "legendFormat": "p95 latency"
      }]
    },
    {
      "title": "Error Rate",
      "type": "timeseries",
      "targets": [{
        "expr": "rate(llm_requests_total{status='error'}[5m]) / rate(llm_requests_total[5m]) * 100",
        "legendFormat": "Error %"
      }]
    },
    {
      "title": "Tokens Per Hour",
      "type": "timeseries",
      "targets": [{
        "expr": "increase(tokens_used_total[1h])",
        "legendFormat": "{{model}} {{type}}"
      }]
    }
  ]
}
```

---

## 6. Jaeger (Free Tracing UI)

```yaml
# Add to docker-compose.yml
jaeger:
  image: jaegertracing/all-in-one:latest
  ports:
    - "16686:16686"  # Jaeger UI
    - "4317:4317"    # OTLP gRPC
    - "4318:4318"    # OTLP HTTP
  environment:
    - COLLECTOR_OTLP_ENABLED=true
```

Access: http://localhost:16686

---

## 7. Complete Docker Compose with Full Observability

```yaml
# docker-compose.yml — Full observability stack
version: "3.9"
services:
  api:
    build: .
    ports: ["8000:8000"]
    environment:
      OTLP_ENDPOINT: http://jaeger:4317
      REDIS_URL: redis://redis:6379
    depends_on: [redis, jaeger]

  redis:
    image: redis:7-alpine
    ports: ["6379:6379"]

  jaeger:
    image: jaegertracing/all-in-one:latest
    ports:
      - "16686:16686"  # UI → http://localhost:16686
      - "4317:4317"    # OTLP

  prometheus:
    image: prom/prometheus:latest
    ports: ["9090:9090"]   # UI → http://localhost:9090
    volumes:
      - ./observability/prometheus.yml:/etc/prometheus/prometheus.yml

  grafana:
    image: grafana/grafana:latest
    ports: ["3000:3000"]   # UI → http://localhost:3000 (admin/admin)
    environment:
      - GF_SECURITY_ADMIN_PASSWORD=admin
    volumes:
      - grafana_data:/var/lib/grafana

volumes:
  grafana_data:
```

---

## 8. Key Prometheus Queries to Know

```promql
# Request rate (per second, 5-min window)
rate(http_requests_total[5m])

# Error rate percentage
rate(http_requests_total{status_code=~"5.."}[5m]) / rate(http_requests_total[5m]) * 100

# P50/P95/P99 latency
histogram_quantile(0.95, rate(http_request_duration_seconds_bucket[5m]))

# LLM tokens per hour by model
increase(tokens_used_total[1h]) by (model)

# Average LLM latency
rate(llm_latency_seconds_sum[5m]) / rate(llm_latency_seconds_count[5m])

# Active conversations
active_conversations_total

# Documents in vector DB
vector_db_document_count
```

---

## Golden Signals to Always Monitor

| Signal | Metric | Alert If |
|--------|--------|----------|
| **Latency** | P95 response time | > 3 seconds |
| **Traffic** | Requests per second | Sudden spike/drop |
| **Errors** | 5xx error rate | > 1% |
| **Saturation** | CPU/Memory usage | > 80% |
| **LLM Health** | LLM error rate | > 5% |
| **Token Usage** | Tokens/hour | Unexpected spike |
