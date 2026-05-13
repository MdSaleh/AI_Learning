"""Tests for the RAG Document Q&A API."""
import io
import pytest
from httpx import ASGITransport, AsyncClient
from unittest.mock import AsyncMock, MagicMock, patch


@pytest.fixture
async def client():
    from app.main import app
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test"
    ) as c:
        yield c


class TestHealth:
    async def test_health_ok(self, client):
        response = await client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert "documents_indexed" in data


class TestDocumentUpload:
    async def test_upload_txt_file(self, client):
        content = b"Machine learning is a type of artificial intelligence."
        response = await client.post(
            "/documents/upload",
            files={"file": ("test.txt", io.BytesIO(content), "text/plain")},
        )
        assert response.status_code == 200
        data = response.json()
        assert "doc_id" in data
        assert data["status"] == "processing"
        assert data["filename"] == "test.txt"
        assert data["size_bytes"] == len(content)

    async def test_upload_rejects_unsupported_type(self, client):
        response = await client.post(
            "/documents/upload",
            files={"file": ("test.jpg", io.BytesIO(b"fake image"), "image/jpeg")},
        )
        assert response.status_code == 415

    async def test_upload_rejects_too_large(self, client):
        big_content = b"x" * (51 * 1024 * 1024)  # 51 MB
        response = await client.post(
            "/documents/upload",
            files={"file": ("big.txt", io.BytesIO(big_content), "text/plain")},
        )
        assert response.status_code == 413


class TestAsk:
    async def test_ask_returns_200(self, client):
        response = await client.post(
            "/ask",
            json={"question": "What is machine learning?"}
        )
        assert response.status_code == 200

    async def test_ask_response_structure(self, client):
        response = await client.post(
            "/ask",
            json={"question": "Explain artificial intelligence"}
        )
        data = response.json()
        assert "answer" in data
        assert "sources" in data
        assert "chunks_used" in data
        assert "top_similarity" in data
        assert "latency_ms" in data

    async def test_ask_rejects_short_question(self, client):
        response = await client.post(
            "/ask",
            json={"question": "hi"}
        )
        assert response.status_code == 422

    async def test_ask_invalid_similarity_threshold(self, client):
        response = await client.post(
            "/ask",
            json={"question": "What is AI?", "min_similarity": 1.5}
        )
        assert response.status_code == 422


class TestDocumentList:
    async def test_list_documents(self, client):
        response = await client.get("/documents")
        assert response.status_code == 200
        data = response.json()
        assert "documents" in data
        assert "total_documents" in data
        assert "total_chunks" in data


class TestChunking:
    def test_chunk_short_text(self):
        from app.ingestion.pipeline import chunk_text
        short = "Hello world. This is a test."
        chunks = chunk_text(short, chunk_size=600)
        assert len(chunks) == 1
        assert chunks[0] == short

    def test_chunk_long_text(self):
        from app.ingestion.pipeline import chunk_text
        long = "This is a sentence. " * 100
        chunks = chunk_text(long, chunk_size=200, overlap=50)
        assert len(chunks) > 1
        assert all(len(c) > 0 for c in chunks)

    def test_clean_text(self):
        from app.ingestion.pipeline import clean_text
        messy = "Hello   world\n\n\n\nTest   text"
        clean = clean_text(messy)
        assert "   " not in clean
        assert "\n\n\n" not in clean
