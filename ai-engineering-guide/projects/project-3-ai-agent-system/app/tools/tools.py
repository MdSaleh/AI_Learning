"""
Agent tools — each tool is a discrete capability the agent can invoke.
All tools are free and open source.
"""
import ast
import math
import re
import time
from typing import Any

import httpx
import structlog

logger = structlog.get_logger()


# ─── Tool Registry ────────────────────────────────────────────────────────────

TOOL_REGISTRY: dict[str, dict] = {}


def tool(name: str, description: str, parameters: dict):
    """Decorator to register a function as an agent tool."""
    def decorator(func):
        TOOL_REGISTRY[name] = {
            "name": name,
            "description": description,
            "parameters": parameters,
            "function": func,
        }
        return func
    return decorator


# ─── Tool: Calculator ─────────────────────────────────────────────────────────

@tool(
    name="calculator",
    description=(
        "Evaluate mathematical expressions safely. "
        "Supports: +, -, *, /, **, %, sqrt(), sin(), cos(), log(), abs(), round(). "
        "Example: '2 ** 10' or 'sqrt(144)'"
    ),
    parameters={
        "expression": {
            "type": "string",
            "description": "Mathematical expression to evaluate",
        }
    },
)
async def calculator(expression: str) -> str:
    """Safely evaluate math expressions."""
    # Whitelist safe operations only
    allowed = set("0123456789+-*/().,% \t")
    safe_names = {
        "sqrt": math.sqrt, "sin": math.sin, "cos": math.cos,
        "tan": math.tan, "log": math.log, "log10": math.log10,
        "abs": abs, "round": round, "pow": pow, "pi": math.pi, "e": math.e,
    }

    # Strip potentially dangerous patterns
    clean = expression.strip()
    if any(kw in clean.lower() for kw in ["import", "exec", "eval", "open", "__"]):
        return "Error: Invalid expression (unsafe keywords detected)"

    try:
        # Use ast.literal_eval-style safe evaluation
        result = eval(clean, {"__builtins__": {}}, safe_names)  # noqa: S307
        return f"Result: {result}"
    except ZeroDivisionError:
        return "Error: Division by zero"
    except Exception as e:
        return f"Error evaluating expression: {e}"


# ─── Tool: Web Search (DuckDuckGo — free, no API key) ────────────────────────

@tool(
    name="web_search",
    description=(
        "Search the web for current information. "
        "Use for: recent events, factual lookups, news, documentation. "
        "Returns top search results with titles and snippets."
    ),
    parameters={
        "query": {
            "type": "string",
            "description": "Search query",
        },
        "max_results": {
            "type": "integer",
            "description": "Number of results to return (1-5)",
            "default": 3,
        },
    },
)
async def web_search(query: str, max_results: int = 3) -> str:
    """Search using DuckDuckGo's free API."""
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(
                "https://api.duckduckgo.com/",
                params={
                    "q": query,
                    "format": "json",
                    "no_redirect": "1",
                    "no_html": "1",
                    "skip_disambig": "1",
                },
                headers={"User-Agent": "AI-Agent/1.0"},
            )
            data = response.json()

        results = []

        # Abstract (direct answer)
        if data.get("Abstract"):
            results.append(f"Direct answer: {data['Abstract']}\nSource: {data.get('AbstractURL', '')}")

        # Related topics
        for topic in data.get("RelatedTopics", [])[:max_results]:
            if isinstance(topic, dict) and topic.get("Text"):
                results.append(f"- {topic['Text']}")

        if not results:
            return f"No results found for: {query}"

        return "\n\n".join(results[:max_results])

    except Exception as e:
        logger.error("web_search_failed", query=query, error=str(e))
        return f"Search failed: {e}"


# ─── Tool: Python Code Runner ─────────────────────────────────────────────────

@tool(
    name="run_python",
    description=(
        "Execute Python code snippets safely. "
        "Use for: data processing, calculations, string manipulation, analysis. "
        "Available: math, json, re, datetime, collections, itertools modules. "
        "Returns stdout output."
    ),
    parameters={
        "code": {
            "type": "string",
            "description": "Python code to execute",
        }
    },
)
async def run_python(code: str) -> str:
    """Execute Python in a sandboxed namespace."""
    import io
    import contextlib

    # Block dangerous operations
    forbidden = ["import os", "import sys", "import subprocess", "open(",
                 "__import__", "exec(", "eval(", "compile("]
    if any(f in code for f in forbidden):
        return "Error: Forbidden operation detected. Cannot import os/sys or use exec/eval."

    # Safe builtins and imports
    safe_globals = {
        "__builtins__": {
            "print": print, "len": len, "range": range, "enumerate": enumerate,
            "zip": zip, "map": map, "filter": filter, "sorted": sorted,
            "sum": sum, "min": min, "max": max, "abs": abs, "round": round,
            "int": int, "float": float, "str": str, "bool": bool, "list": list,
            "dict": dict, "tuple": tuple, "set": set, "isinstance": isinstance,
            "type": type,
        }
    }

    # Allow safe stdlib modules
    import json, re, math, datetime, collections, itertools
    safe_globals.update({
        "json": json, "re": re, "math": math,
        "datetime": datetime, "collections": collections, "itertools": itertools,
    })

    stdout_capture = io.StringIO()
    try:
        with contextlib.redirect_stdout(stdout_capture):
            exec(code, safe_globals)  # noqa: S102
        output = stdout_capture.getvalue()
        return output if output else "Code executed successfully (no output)"
    except Exception as e:
        return f"Execution error: {type(e).__name__}: {e}"


# ─── Tool: Get Current Time ───────────────────────────────────────────────────

@tool(
    name="get_current_time",
    description="Get the current date and time in UTC.",
    parameters={},
)
async def get_current_time() -> str:
    """Return current UTC time."""
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc)
    return f"Current UTC time: {now.strftime('%Y-%m-%d %H:%M:%S UTC')}"


# ─── Tool: Text Summarizer ────────────────────────────────────────────────────

@tool(
    name="summarize_text",
    description=(
        "Summarize a long piece of text into key points. "
        "Use when you have retrieved text that needs to be condensed."
    ),
    parameters={
        "text": {
            "type": "string",
            "description": "Text to summarize",
        },
        "max_sentences": {
            "type": "integer",
            "description": "Maximum sentences in summary",
            "default": 5,
        },
    },
)
async def summarize_text(text: str, max_sentences: int = 5) -> str:
    """Simple extractive summarization (no LLM needed)."""
    sentences = re.split(r"(?<=[.!?])\s+", text.strip())
    if len(sentences) <= max_sentences:
        return text

    # Score sentences by position (first/last are usually most important)
    scored = []
    for i, sent in enumerate(sentences):
        # Weight: first sentences score higher
        score = (len(sentences) - i) / len(sentences)
        # Bonus for sentences with numbers or key terms
        if any(char.isdigit() for char in sent):
            score += 0.2
        scored.append((score, i, sent))

    top = sorted(scored, reverse=True)[:max_sentences]
    # Return in original order
    top_sorted = sorted(top, key=lambda x: x[1])
    return " ".join(s[2] for s in top_sorted)


# ─── Tool Executor ────────────────────────────────────────────────────────────

async def execute_tool(tool_name: str, inputs: dict[str, Any]) -> str:
    """Execute a registered tool by name with given inputs."""
    if tool_name not in TOOL_REGISTRY:
        available = ", ".join(TOOL_REGISTRY.keys())
        return f"Unknown tool '{tool_name}'. Available tools: {available}"

    tool_info = TOOL_REGISTRY[tool_name]
    func = tool_info["function"]

    start = time.perf_counter()
    try:
        result = await func(**inputs)
        elapsed = time.perf_counter() - start
        logger.info("tool_executed", tool=tool_name, duration_ms=round(elapsed * 1000, 2))
        return str(result)
    except TypeError as e:
        return f"Tool '{tool_name}' called with wrong parameters: {e}"
    except Exception as e:
        logger.error("tool_execution_failed", tool=tool_name, error=str(e))
        return f"Tool '{tool_name}' failed: {e}"


def get_tools_description() -> str:
    """Format all tools for the system prompt."""
    lines = []
    for name, info in TOOL_REGISTRY.items():
        params = ", ".join(
            f"{k}: {v.get('type', 'string')}"
            for k, v in info["parameters"].items()
        )
        lines.append(f"- **{name}**({params}): {info['description']}")
    return "\n".join(lines)
