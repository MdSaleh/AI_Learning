"""Pytest configuration and shared fixtures."""
import os
import pytest

# Set test environment before any imports
os.environ["MOCK_LLM"] = "true"
os.environ["ENV"] = "test"
os.environ["REDIS_URL"] = "redis://localhost:6379"

@pytest.fixture(scope="session")
def anyio_backend():
    return "asyncio"
