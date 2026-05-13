"""
AI Chat API — Main application entry point.

Run with:
    uvicorn app.main:app --reload --port 8000

Then visit:
    http://localhost:8000/docs  (Swagger UI)
    http://localhost:8000/redoc (ReDoc)
"""
import logging
import sys
import time
import uuid
from contextlib import asynccontextmanager
from typing import AsyncGenerator

import redis.asyncio as aioredis
import structlog
from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse
from prometheus_client import (
    CONTENT_TYPE_LATEST,
    Counter,
    Histogram,
    generate_latest,
)

from app.api.v1.chat import router as chat_router
from app.core.config import get_settings
from app.models.schemas import HealthResponse
from app.services.llm import LLMService

settings = get_settings()

# ─── Logging setup ────────────────────────────────────────────────────────────
def setup_logging() -> None:
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=getattr(logging, settings.log_level.upper()),
    )

    processors = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
    ]

    if settings.environment == "development":
        processors.append(structlog.dev.ConsoleRenderer(colors=True))
    else:
        processors.extend([
            structlog.processors.dict_tracebacks,
            structlog.processors.JSONRenderer(),
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


# ─── Prometheus metrics ───────────────────────────────────────────────────────
REQUEST_COUNT = Counter(
    "http_requests_total",
    "Total HTTP requests",
    ["method", "endpoint", "status_code"],
)
REQUEST_DURATION = Histogram(
    "http_request_duration_seconds",
    "HTTP request duration in seconds",
    ["method", "endpoint"],
    buckets=[0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0],
)

logger = structlog.get_logger()


# ─── Lifespan ─────────────────────────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application startup and shutdown logic."""
    setup_logging()

    logger.info(
        "starting_up",
        app=settings.app_name,
        environment=settings.environment,
        port=settings.port,
    )

    # Initialize LLM service
    llm_service = LLMService()
    app.state.llm_service = llm_service

    # Test Ollama connection
    if await llm_service.health_check():
        logger.info("llm_service_ready", model=settings.default_model)
    else:
        logger.warning("llm_not_available_starting_in_degraded_mode")

    # Test Redis connection
    try:
        redis_client = aioredis.from_url(settings.redis_url)
        await redis_client.ping()
        await redis_client.aclose()
        logger.info("redis_connected", url=settings.redis_url)
    except Exception as e:
        logger.warning("redis_not_available", error=str(e))

    logger.info("startup_complete")
    yield

    # Shutdown
    logger.info("shutting_down")


# ─── App factory ──────────────────────────────────────────────────────────────
def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.app_name,
        description="""
## AI Chat API

A production-grade streaming chat API powered by local LLMs via Ollama.

### Features
- 🤖 Multi-turn conversations with memory
- ⚡ Streaming responses (Server-Sent Events)
- 📊 Prometheus metrics at `/metrics`
- 🔍 Request tracing via X-Request-ID header
- 🐳 Docker ready

### Quick Start
1. Start Ollama: `ollama serve && ollama pull llama3.1:8b`
2. Send a message: `POST /api/v1/chat`
3. Stream a response: `POST /api/v1/chat/stream`
        """,
        version="1.0.0",
        docs_url="/docs",
        redoc_url="/redoc",
        lifespan=lifespan,
    )

    # ─── Middleware ────────────────────────────────────────────────────────────
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.add_middleware(GZipMiddleware, minimum_size=1000)

    @app.middleware("http")
    async def observability_middleware(request: Request, call_next: any) -> Response:
        """Add request ID, metrics, and structured logging to every request."""
        request_id = str(uuid.uuid4())
        request.state.request_id = request_id

        # Bind context vars (available in all log calls during this request)
        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(
            request_id=request_id,
            method=request.method,
            path=request.url.path,
        )

        logger.info("request_started")
        start = time.perf_counter()

        try:
            response = await call_next(request)
            duration = time.perf_counter() - start

            # Normalize path for metrics (avoid high cardinality from IDs)
            path = request.url.path
            if any(char.isdigit() for char in path.split("/")[-1]):
                path = "/".join(path.split("/")[:-1]) + "/{id}"

            REQUEST_COUNT.labels(
                method=request.method,
                endpoint=path,
                status_code=str(response.status_code),
            ).inc()
            REQUEST_DURATION.labels(
                method=request.method,
                endpoint=path,
            ).observe(duration)

            logger.info(
                "request_completed",
                status_code=response.status_code,
                duration_ms=round(duration * 1000, 2),
            )

            response.headers["X-Request-ID"] = request_id
            return response

        except Exception as e:
            duration = time.perf_counter() - start
            logger.error(
                "request_failed",
                error=str(e),
                duration_ms=round(duration * 1000, 2),
            )
            raise

    # ─── Routers ──────────────────────────────────────────────────────────────
    app.include_router(chat_router, prefix="/api/v1")

    # ─── System endpoints ──────────────────────────────────────────────────────
    @app.get("/health", response_model=HealthResponse, tags=["System"])
    async def health_check() -> HealthResponse:
        """Health check — used by load balancers and monitoring."""
        llm_ok = False
        redis_ok = False

        try:
            llm_service: LLMService = app.state.llm_service
            llm_ok = await llm_service.health_check()
        except Exception:
            pass

        try:
            client = aioredis.from_url(settings.redis_url)
            await client.ping()
            await client.aclose()
            redis_ok = True
        except Exception:
            pass

        overall = "healthy" if (llm_ok and redis_ok) else "degraded"

        return HealthResponse(
            status=overall,
            service=settings.app_name,
            ollama_connected=llm_ok,
            redis_connected=redis_ok,
        )

    @app.get("/metrics", tags=["System"])
    async def prometheus_metrics() -> Response:
        """Prometheus metrics endpoint — scrape this with Prometheus."""
        return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)

    @app.get("/", tags=["System"])
    async def root() -> dict:
        return {
            "service": settings.app_name,
            "version": "1.0.0",
            "docs": "/docs",
            "health": "/health",
        }

    # ─── Error handlers ───────────────────────────────────────────────────────
    @app.exception_handler(Exception)
    async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        logger.error("unhandled_exception", error=str(exc), exc_info=True)
        return JSONResponse(
            status_code=500,
            content={
                "error": "internal_server_error",
                "message": "An unexpected error occurred",
                "request_id": getattr(request.state, "request_id", None),
            },
        )

    return app


app = create_app()


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=settings.port,
        reload=True,
        log_level="info",
    )
