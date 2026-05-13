"""LLM Service — wraps Ollama with retry, metrics, and streaming support."""
import json
import time
from typing import AsyncGenerator, Optional

import httpx
import structlog
from prometheus_client import Counter, Histogram

from app.core.config import get_settings

logger = structlog.get_logger()
settings = get_settings()

# ─── Prometheus metrics ───────────────────────────────────────────────────────
LLM_REQUESTS = Counter(
    "llm_requests_total",
    "Total LLM requests",
    ["model", "type", "status"],
)
LLM_LATENCY = Histogram(
    "llm_latency_seconds",
    "LLM response latency",
    ["model", "type"],
    buckets=[0.1, 0.5, 1.0, 2.0, 5.0, 10.0, 30.0, 60.0],
)
LLM_TOKENS = Counter(
    "llm_tokens_total",
    "Total tokens used",
    ["model", "token_type"],
)


class LLMService:
    """Service for interacting with local Ollama LLM."""

    def __init__(self) -> None:
        self.base_url = settings.ollama_base_url
        self.default_model = settings.default_model
        self.timeout = settings.llm_timeout_seconds
        self._mock = settings.mock_llm

    async def health_check(self) -> bool:
        """Check if Ollama is reachable."""
        if self._mock:
            logger.info("llm_mock_mode_active")
            return True

        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(f"{self.base_url}/api/tags")
                models = response.json().get("models", [])
                model_names = [m["name"] for m in models]
                logger.info("ollama_connected", available_models=model_names)
                return True
        except Exception as e:
            logger.warning("ollama_not_reachable", error=str(e))
            return False

    async def generate(
        self,
        messages: list[dict],
        model: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 2048,
        system_prompt: Optional[str] = None,
    ) -> dict:
        """
        Generate a non-streaming response.

        Args:
            messages: Conversation history [{"role": "user/assistant", "content": "..."}]
            model: Model name (defaults to settings.default_model)
            temperature: Sampling temperature 0-2
            max_tokens: Maximum tokens in response
            system_prompt: Optional system instruction

        Returns:
            dict with response, model, tokens_used, latency_ms
        """
        model = model or self.default_model
        start = time.perf_counter()

        if self._mock:
            return self._mock_response(messages, model)

        try:
            # Build Ollama chat request
            payload = {
                "model": model,
                "messages": messages,
                "stream": False,
                "options": {
                    "temperature": temperature,
                    "num_predict": max_tokens,
                },
            }
            if system_prompt:
                payload["system"] = system_prompt

            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    f"{self.base_url}/api/chat",
                    json=payload,
                )
                response.raise_for_status()
                data = response.json()

            latency = time.perf_counter() - start
            content = data["message"]["content"]

            # Track metrics
            LLM_REQUESTS.labels(model=model, type="chat", status="success").inc()
            LLM_LATENCY.labels(model=model, type="chat").observe(latency)

            # Estimate tokens (Ollama may return eval_count)
            prompt_tokens = data.get("prompt_eval_count", len(str(messages)) // 4)
            completion_tokens = data.get("eval_count", len(content) // 4)
            LLM_TOKENS.labels(model=model, token_type="prompt").inc(prompt_tokens)
            LLM_TOKENS.labels(model=model, token_type="completion").inc(completion_tokens)

            logger.info(
                "llm_generate_complete",
                model=model,
                latency_ms=round(latency * 1000, 2),
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
            )

            return {
                "response": content,
                "model": model,
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
                "total_tokens": prompt_tokens + completion_tokens,
                "latency_ms": round(latency * 1000, 2),
            }

        except httpx.TimeoutException:
            LLM_REQUESTS.labels(model=model, type="chat", status="timeout").inc()
            logger.error("llm_timeout", model=model, timeout=self.timeout)
            raise LLMTimeoutError(f"LLM timed out after {self.timeout}s")

        except httpx.HTTPStatusError as e:
            LLM_REQUESTS.labels(model=model, type="chat", status="http_error").inc()
            logger.error("llm_http_error", model=model, status_code=e.response.status_code)
            raise LLMError(f"LLM returned HTTP {e.response.status_code}")

        except Exception as e:
            LLM_REQUESTS.labels(model=model, type="chat", status="error").inc()
            logger.error("llm_error", model=model, error=str(e), exc_info=True)
            raise LLMError(f"LLM call failed: {e}")

    async def stream(
        self,
        messages: list[dict],
        model: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 2048,
        system_prompt: Optional[str] = None,
    ) -> AsyncGenerator[str, None]:
        """
        Stream response tokens one by one.

        Yields individual tokens as they arrive from the LLM.
        """
        model = model or self.default_model

        if self._mock:
            # Mock streaming
            mock_response = "This is a mock streaming response from the AI. " * 3
            for word in mock_response.split():
                yield word + " "
                import asyncio
                await asyncio.sleep(0.05)
            return

        payload = {
            "model": model,
            "messages": messages,
            "stream": True,
            "options": {
                "temperature": temperature,
                "num_predict": max_tokens,
            },
        }
        if system_prompt:
            payload["system"] = system_prompt

        start = time.perf_counter()
        total_tokens = 0

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                async with client.stream(
                    "POST",
                    f"{self.base_url}/api/chat",
                    json=payload,
                ) as response:
                    response.raise_for_status()

                    async for line in response.aiter_lines():
                        if not line.strip():
                            continue

                        try:
                            data = json.loads(line)
                        except json.JSONDecodeError:
                            continue

                        if data.get("done"):
                            # Final chunk — record metrics
                            latency = time.perf_counter() - start
                            LLM_REQUESTS.labels(model=model, type="stream", status="success").inc()
                            LLM_LATENCY.labels(model=model, type="stream").observe(latency)
                            logger.info(
                                "llm_stream_complete",
                                model=model,
                                latency_ms=round(latency * 1000, 2),
                                total_tokens=total_tokens,
                            )
                            return

                        token = data.get("message", {}).get("content", "")
                        if token:
                            total_tokens += 1
                            yield token

        except httpx.TimeoutException:
            LLM_REQUESTS.labels(model=model, type="stream", status="timeout").inc()
            raise LLMTimeoutError(f"LLM stream timed out")
        except Exception as e:
            LLM_REQUESTS.labels(model=model, type="stream", status="error").inc()
            logger.error("llm_stream_error", error=str(e), exc_info=True)
            raise LLMError(f"LLM stream failed: {e}")

    def _mock_response(self, messages: list[dict], model: str) -> dict:
        """Return mock response for testing."""
        last_message = messages[-1]["content"] if messages else "Hello"
        return {
            "response": f"[MOCK] You said: '{last_message}'. This is a mock AI response.",
            "model": model,
            "prompt_tokens": 10,
            "completion_tokens": 20,
            "total_tokens": 30,
            "latency_ms": 50.0,
        }


# ─── Custom Exceptions ────────────────────────────────────────────────────────
class LLMError(Exception):
    """Base LLM error."""


class LLMTimeoutError(LLMError):
    """LLM call timed out."""


class ModelNotAvailableError(LLMError):
    """Requested model is not available."""
