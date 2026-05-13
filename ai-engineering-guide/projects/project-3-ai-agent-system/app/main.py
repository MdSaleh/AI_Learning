"""AI Agent System — FastAPI application."""
import json
import uuid
from contextlib import asynccontextmanager
from typing import AsyncGenerator, Optional

import structlog
from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest
from pydantic import BaseModel, Field

from app.agents.react_agent import ReActAgent
from app.tools.tools import TOOL_REGISTRY

logger = structlog.get_logger()


# ─── Schemas ──────────────────────────────────────────────────────────────────

class AgentRequest(BaseModel):
    query: str = Field(..., min_length=3, max_length=5000,
                       description="The task or question for the agent",
                       examples=["What is 2^32? Also search for Python 3.12 release date."])
    session_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    model: str = Field(default="llama3.1:8b")
    max_steps: int = Field(default=10, ge=1, le=20)
    temperature: float = Field(default=0.1, ge=0.0, le=1.0)
    stream: bool = Field(default=False)


class AgentResponse(BaseModel):
    final_answer: str
    steps: list[dict]
    tool_calls: list[dict]
    total_steps: int
    total_tokens: int
    latency_ms: float
    model: str
    session_id: str


# ─── Lifespan ─────────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    logger.info("agent_system_starting", tools=list(TOOL_REGISTRY.keys()))
    yield
    logger.info("agent_system_shutdown")


# ─── App ──────────────────────────────────────────────────────────────────────

app = FastAPI(
    title="AI Agent System",
    description="""
A production-grade AI agent that can reason and use tools to answer complex questions.

## How It Works
The agent uses the **ReAct pattern** (Reasoning + Acting):
1. **Think** about what needs to be done
2. **Choose** the right tool
3. **Act** by calling the tool
4. **Observe** the result
5. **Repeat** until a complete answer is reached

## Available Tools
- `calculator` — Safe math evaluation
- `web_search` — DuckDuckGo search (free, no API key)
- `run_python` — Safe Python code execution
- `get_current_time` — Current UTC time
- `summarize_text` — Extract key sentences

## Example Queries
- "What is the square root of 144 times pi? Also what's today's date?"
- "Search for the latest Python version and write code to print fibonacci numbers"
- "Calculate compound interest for $10000 at 5% for 10 years"
    """,
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


# ─── Endpoints ────────────────────────────────────────────────────────────────

@app.post("/agent/run", response_model=AgentResponse, tags=["Agent"])
async def run_agent(request: AgentRequest) -> AgentResponse:
    """
    Run the AI agent on a query.
    The agent will think, use tools, and return a complete answer.
    """
    if request.stream:
        raise Exception("Use /agent/stream for streaming mode")

    log = logger.bind(session_id=request.session_id)
    log.info("agent_run_requested", query=request.query[:80])

    agent = ReActAgent(
        model=request.model,
        max_steps=request.max_steps,
        temperature=request.temperature,
    )

    result = await agent.run(request.query, session_id=request.session_id)

    return AgentResponse(session_id=request.session_id, **result)


@app.post("/agent/stream", tags=["Agent"])
async def stream_agent(request: AgentRequest) -> StreamingResponse:
    """
    Run the agent and stream each step as Server-Sent Events.
    Watch the agent think in real time!
    """
    agent = ReActAgent(
        model=request.model,
        max_steps=request.max_steps,
        temperature=request.temperature,
    )

    async def event_generator() -> AsyncGenerator[str, None]:
        async for event in agent.stream(request.query, session_id=request.session_id):
            yield f"data: {json.dumps(event)}\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive"},
    )


@app.get("/tools", tags=["Tools"])
async def list_tools() -> dict:
    """List all available agent tools."""
    tools = [
        {
            "name": name,
            "description": info["description"],
            "parameters": info["parameters"],
        }
        for name, info in TOOL_REGISTRY.items()
    ]
    return {"tools": tools, "count": len(tools)}


@app.post("/tools/{tool_name}", tags=["Tools"])
async def test_tool(tool_name: str, body: dict) -> dict:
    """
    Test a specific tool directly (without running the full agent).
    Useful for debugging tools.
    """
    from app.tools.tools import execute_tool

    if tool_name not in TOOL_REGISTRY:
        from fastapi import HTTPException
        raise HTTPException(404, f"Tool '{tool_name}' not found")

    result = await execute_tool(tool_name, body)
    return {"tool": tool_name, "input": body, "result": result}


@app.get("/health", tags=["System"])
async def health() -> dict:
    return {
        "status": "healthy",
        "service": "AI Agent System",
        "available_tools": list(TOOL_REGISTRY.keys()),
    }


@app.get("/metrics", tags=["System"])
async def metrics() -> Response:
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)
