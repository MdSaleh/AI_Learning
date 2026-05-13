"""
ReAct Agent — Reasoning + Acting loop.
The agent thinks, picks tools, acts, observes, and repeats until done.
"""
import json
import re
import time
from enum import Enum
from typing import AsyncGenerator, Optional

import httpx
import structlog
from prometheus_client import Counter, Histogram

from app.tools.tools import TOOL_REGISTRY, execute_tool, get_tools_description

logger = structlog.get_logger()

AGENT_STEPS = Counter("agent_steps_total", "Total agent reasoning steps", ["type"])
AGENT_LATENCY = Histogram(
    "agent_run_latency_seconds",
    "End-to-end agent run latency",
    buckets=[0.5, 1.0, 2.0, 5.0, 10.0, 30.0, 60.0],
)
AGENT_TOOL_CALLS = Counter("agent_tool_calls_total", "Tool calls by name", ["tool", "status"])


class StepType(str, Enum):
    THOUGHT = "thought"
    ACTION = "action"
    OBSERVATION = "observation"
    FINAL_ANSWER = "final_answer"
    ERROR = "error"


class AgentStep:
    def __init__(self, step_type: StepType, content: str, tool: str = "", tool_input: dict = None):
        self.step_type = step_type
        self.content = content
        self.tool = tool
        self.tool_input = tool_input or {}
        self.timestamp = time.time()

    def to_dict(self) -> dict:
        return {
            "type": self.step_type.value,
            "content": self.content,
            "tool": self.tool,
            "tool_input": self.tool_input,
        }


SYSTEM_PROMPT_TEMPLATE = """You are a highly capable AI agent with access to tools.

## Available Tools
{tools}

## Instructions
Answer the user's question by reasoning step by step and using tools when needed.

Respond using EXACTLY this format (no deviations):

THOUGHT: <your reasoning about what to do next>
ACTION: <tool_name>
INPUT: <JSON object with tool inputs>

OR when you have the final answer:

THOUGHT: <your final reasoning>
FINAL_ANSWER: <complete answer to the user's question>

## Rules
- Always start your response with THOUGHT:
- Use FINAL_ANSWER: only when you have a complete answer
- INPUT must be valid JSON
- If a tool fails, try a different approach
- Be concise but complete in your final answer
- Cite tool results when relevant
"""


class ReActAgent:
    """
    ReAct (Reasoning + Acting) agent.

    Iterates: Think → Act → Observe → Think → ... → Final Answer
    """

    def __init__(
        self,
        ollama_url: str = "http://localhost:11434",
        model: str = "llama3.1:8b",
        max_steps: int = 10,
        temperature: float = 0.1,
    ) -> None:
        self.ollama_url = ollama_url
        self.model = model
        self.max_steps = max_steps
        self.temperature = temperature

    async def run(
        self,
        user_query: str,
        session_id: str = "default",
    ) -> dict:
        """
        Run the agent on a user query.

        Returns:
            dict with final_answer, steps, tool_calls, total_tokens, latency_ms
        """
        start = time.perf_counter()
        log = logger.bind(session_id=session_id, query=user_query[:80])
        log.info("agent_run_started")

        system_prompt = SYSTEM_PROMPT_TEMPLATE.format(
            tools=get_tools_description()
        )

        # Conversation history (grows with each step)
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_query},
        ]

        steps: list[AgentStep] = []
        tool_calls_made = []
        total_tokens = 0

        for step_num in range(self.max_steps):
            log.debug("agent_step", step=step_num + 1)

            # ── LLM call ──
            llm_response, tokens = await self._call_llm(messages)
            total_tokens += tokens

            # ── Parse response ──
            parsed = self._parse_response(llm_response)

            if parsed["type"] == "final_answer":
                steps.append(AgentStep(StepType.THOUGHT, parsed.get("thought", "")))
                steps.append(AgentStep(StepType.FINAL_ANSWER, parsed["final_answer"]))
                AGENT_STEPS.labels(type="final_answer").inc()

                latency = time.perf_counter() - start
                AGENT_LATENCY.observe(latency)

                log.info(
                    "agent_run_complete",
                    steps_taken=step_num + 1,
                    tool_calls=len(tool_calls_made),
                    latency_ms=round(latency * 1000, 2),
                )

                return {
                    "final_answer": parsed["final_answer"],
                    "steps": [s.to_dict() for s in steps],
                    "tool_calls": tool_calls_made,
                    "total_steps": step_num + 1,
                    "total_tokens": total_tokens,
                    "latency_ms": round(latency * 1000, 2),
                    "model": self.model,
                }

            elif parsed["type"] == "action":
                thought = parsed.get("thought", "")
                tool_name = parsed.get("tool", "")
                tool_input = parsed.get("input", {})

                steps.append(AgentStep(StepType.THOUGHT, thought))
                steps.append(AgentStep(StepType.ACTION, f"Using {tool_name}", tool_name, tool_input))

                AGENT_STEPS.labels(type="action").inc()

                # ── Execute tool ──
                observation = await execute_tool(tool_name, tool_input)
                steps.append(AgentStep(StepType.OBSERVATION, observation))

                tool_calls_made.append({
                    "tool": tool_name,
                    "input": tool_input,
                    "output": observation[:200],
                })
                AGENT_TOOL_CALLS.labels(tool=tool_name, status="success").inc()

                # Add to conversation so LLM knows what happened
                messages.append({"role": "assistant", "content": llm_response})
                messages.append({
                    "role": "user",
                    "content": f"OBSERVATION: {observation}"
                })

            else:
                # Parsing failed — tell the agent
                log.warning("parse_failed", raw=llm_response[:200])
                messages.append({"role": "assistant", "content": llm_response})
                messages.append({
                    "role": "user",
                    "content": "Your response format was incorrect. Please use THOUGHT: then either ACTION:/INPUT: or FINAL_ANSWER:"
                })
                AGENT_STEPS.labels(type="parse_error").inc()

        # Max steps reached
        latency = time.perf_counter() - start
        log.warning("agent_max_steps_reached", steps=self.max_steps)
        return {
            "final_answer": "I wasn't able to complete the task within the allowed steps. Please try a simpler question.",
            "steps": [s.to_dict() for s in steps],
            "tool_calls": tool_calls_made,
            "total_steps": self.max_steps,
            "total_tokens": total_tokens,
            "latency_ms": round(latency * 1000, 2),
            "model": self.model,
        }

    async def stream(
        self,
        user_query: str,
        session_id: str = "default",
    ) -> AsyncGenerator[dict, None]:
        """
        Stream agent steps as they happen.
        Useful for showing the agent "thinking" in real time.
        """
        yield {"event": "started", "query": user_query}

        result = await self.run(user_query, session_id)

        for step in result["steps"]:
            yield {"event": "step", "step": step}

        yield {
            "event": "complete",
            "final_answer": result["final_answer"],
            "tool_calls": result["tool_calls"],
            "total_steps": result["total_steps"],
            "latency_ms": result["latency_ms"],
        }

    def _parse_response(self, response: str) -> dict:
        """Parse the agent's structured response."""
        response = response.strip()

        # Extract THOUGHT
        thought_match = re.search(r"THOUGHT:\s*(.+?)(?=ACTION:|FINAL_ANSWER:|$)", response, re.DOTALL)
        thought = thought_match.group(1).strip() if thought_match else ""

        # Check for FINAL_ANSWER
        if "FINAL_ANSWER:" in response:
            final = re.search(r"FINAL_ANSWER:\s*(.+)", response, re.DOTALL)
            if final:
                return {
                    "type": "final_answer",
                    "thought": thought,
                    "final_answer": final.group(1).strip(),
                }

        # Check for ACTION
        action_match = re.search(r"ACTION:\s*(\w+)", response)
        input_match = re.search(r"INPUT:\s*(\{.+?\})", response, re.DOTALL)

        if action_match:
            tool_name = action_match.group(1).strip()
            tool_input = {}
            if input_match:
                try:
                    tool_input = json.loads(input_match.group(1))
                except json.JSONDecodeError:
                    # Try to extract as key: value pairs
                    tool_input = {}

            return {
                "type": "action",
                "thought": thought,
                "tool": tool_name,
                "input": tool_input,
            }

        return {"type": "unknown", "raw": response}

    async def _call_llm(self, messages: list[dict]) -> tuple[str, int]:
        """Call Ollama LLM with the current conversation."""
        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.post(
                f"{self.ollama_url}/api/chat",
                json={
                    "model": self.model,
                    "messages": messages,
                    "stream": False,
                    "options": {
                        "temperature": self.temperature,
                        "num_predict": 1024,
                    },
                },
            )
            response.raise_for_status()
            data = response.json()

        content = data["message"]["content"]
        tokens = data.get("eval_count", len(content) // 4)
        return content, tokens
