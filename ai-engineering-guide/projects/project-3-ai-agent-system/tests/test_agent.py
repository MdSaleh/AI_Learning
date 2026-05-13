"""Tests for the AI Agent System."""
import pytest
from httpx import ASGITransport, AsyncClient
from unittest.mock import AsyncMock, patch


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
        assert "available_tools" in data

    async def test_tools_listed(self, client):
        response = await client.get("/tools")
        assert response.status_code == 200
        data = response.json()
        assert len(data["tools"]) > 0
        tool_names = [t["name"] for t in data["tools"]]
        assert "calculator" in tool_names
        assert "web_search" in tool_names
        assert "run_python" in tool_names


class TestTools:
    async def test_calculator_tool(self, client):
        response = await client.post(
            "/tools/calculator",
            json={"expression": "2 ** 10"}
        )
        assert response.status_code == 200
        data = response.json()
        assert "1024" in data["result"]

    async def test_calculator_math(self, client):
        response = await client.post(
            "/tools/calculator",
            json={"expression": "sqrt(144)"}
        )
        data = response.json()
        assert "12" in data["result"]

    async def test_calculator_blocks_dangerous(self, client):
        response = await client.post(
            "/tools/calculator",
            json={"expression": "__import__('os').system('ls')"}
        )
        data = response.json()
        assert "Error" in data["result"]

    async def test_python_runner(self, client):
        response = await client.post(
            "/tools/run_python",
            json={"code": "print([i**2 for i in range(5)])"}
        )
        assert response.status_code == 200
        data = response.json()
        assert "[0, 1, 4, 9, 16]" in data["result"]

    async def test_python_blocks_os_import(self, client):
        response = await client.post(
            "/tools/run_python",
            json={"code": "import os; os.system('ls')"}
        )
        data = response.json()
        assert "Forbidden" in data["result"] or "Error" in data["result"]

    async def test_time_tool(self, client):
        response = await client.post("/tools/get_current_time", json={})
        data = response.json()
        assert "UTC" in data["result"]

    async def test_unknown_tool_returns_404(self, client):
        response = await client.post(
            "/tools/nonexistent_tool",
            json={}
        )
        assert response.status_code == 404


class TestAgentParsing:
    def test_parse_final_answer(self):
        from app.agents.react_agent import ReActAgent
        agent = ReActAgent()
        response = """THOUGHT: I have enough information to answer.
FINAL_ANSWER: The answer is 42."""
        parsed = agent._parse_response(response)
        assert parsed["type"] == "final_answer"
        assert "42" in parsed["final_answer"]

    def test_parse_action(self):
        from app.agents.react_agent import ReActAgent
        agent = ReActAgent()
        response = """THOUGHT: I should calculate this.
ACTION: calculator
INPUT: {"expression": "2 ** 8"}"""
        parsed = agent._parse_response(response)
        assert parsed["type"] == "action"
        assert parsed["tool"] == "calculator"
        assert parsed["input"]["expression"] == "2 ** 8"

    def test_parse_unknown_format(self):
        from app.agents.react_agent import ReActAgent
        agent = ReActAgent()
        response = "This doesn't follow the format at all"
        parsed = agent._parse_response(response)
        assert parsed["type"] == "unknown"
