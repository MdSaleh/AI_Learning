"""Tests for the AI Chat API."""
import pytest
from httpx import ASGITransport, AsyncClient
from unittest.mock import AsyncMock, MagicMock, patch


@pytest.fixture
def mock_llm_response():
    return {
        "response": "Machine learning is a subset of AI that enables computers to learn from data.",
        "model": "llama3.1:8b",
        "prompt_tokens": 15,
        "completion_tokens": 20,
        "total_tokens": 35,
        "latency_ms": 450.0,
    }


@pytest.fixture
async def client():
    """Create test client with mocked dependencies."""
    import os
    os.environ["MOCK_LLM"] = "true"
    os.environ["ENV"] = "test"

    from app.main import create_app
    app = create_app()

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test"
    ) as c:
        yield c


class TestHealth:
    async def test_health_returns_200(self, client):
        response = await client.get("/health")
        assert response.status_code == 200

    async def test_health_has_required_fields(self, client):
        data = (await client.get("/health")).json()
        assert "status" in data
        assert "service" in data
        assert "ollama_connected" in data
        assert "redis_connected" in data

    async def test_root_returns_200(self, client):
        response = await client.get("/")
        assert response.status_code == 200


class TestChat:
    async def test_chat_returns_200(self, client):
        response = await client.post(
            "/api/v1/chat",
            json={"message": "Hello AI!"}
        )
        assert response.status_code == 200

    async def test_chat_response_has_required_fields(self, client):
        response = await client.post(
            "/api/v1/chat",
            json={"message": "What is Python?"}
        )
        data = response.json()
        assert "response" in data
        assert "conversation_id" in data
        assert "model" in data
        assert "total_tokens" in data
        assert "latency_ms" in data

    async def test_chat_rejects_empty_message(self, client):
        response = await client.post(
            "/api/v1/chat",
            json={"message": ""}
        )
        assert response.status_code == 422

    async def test_chat_rejects_whitespace_message(self, client):
        response = await client.post(
            "/api/v1/chat",
            json={"message": "   "}
        )
        assert response.status_code == 422

    async def test_chat_rejects_invalid_temperature(self, client):
        response = await client.post(
            "/api/v1/chat",
            json={"message": "Hello", "temperature": 5.0}
        )
        assert response.status_code == 422

    async def test_chat_conversation_id_returned(self, client):
        response = await client.post(
            "/api/v1/chat",
            json={"message": "Hello", "conversation_id": "test-conv-123"}
        )
        data = response.json()
        assert data["conversation_id"] == "test-conv-123"

    async def test_chat_autogenerates_conversation_id(self, client):
        response = await client.post(
            "/api/v1/chat",
            json={"message": "Hello"}
        )
        data = response.json()
        assert len(data["conversation_id"]) > 0

    async def test_request_id_in_response_headers(self, client):
        response = await client.post(
            "/api/v1/chat",
            json={"message": "Hello"}
        )
        assert "x-request-id" in response.headers

    async def test_metrics_endpoint(self, client):
        response = await client.get("/metrics")
        assert response.status_code == 200
        assert "http_requests_total" in response.text


class TestConversationHistory:
    async def test_get_nonexistent_conversation_returns_404(self, client):
        response = await client.get("/api/v1/chat/nonexistent-id-999")
        # Either 404 (not found) or depends on Redis being up
        assert response.status_code in [404, 503]

    async def test_clear_nonexistent_conversation(self, client):
        response = await client.delete("/api/v1/chat/nonexistent-id-999")
        assert response.status_code in [200, 503]
