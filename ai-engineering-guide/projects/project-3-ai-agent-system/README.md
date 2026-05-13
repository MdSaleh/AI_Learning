# 🤖 Project 3: AI Agent System

## What You'll Build
- ReAct (Reasoning + Acting) agent
- Built-in tools: calculator, web search, Python runner, time
- Streaming — watch the agent think step by step
- Full test suite + CI/CD with GitHub Actions

## Run It
```bash
# 1. Start Ollama
ollama serve && ollama pull llama3.1:8b

# 2. Install and run
python -m venv .venv && source .venv/bin/activate
pip install uv && uv pip install -e ".[dev]"
uvicorn app.main:app --reload --port 8002

# 3. Run the agent
curl -X POST http://localhost:8002/agent/run \
  -H "Content-Type: application/json" \
  -d '{"query": "What is 2^32? Also what day of the week is today?"}'

# 4. List available tools
curl http://localhost:8002/tools

# 5. Test a tool directly
curl -X POST http://localhost:8002/tools/calculator \
  -H "Content-Type: application/json" \
  -d '{"expression": "sqrt(144) * pi"}'
```

## How It Works (ReAct Pattern)
1. Agent receives your query
2. THINKS about what tool to use
3. ACTS by calling the tool
4. OBSERVES the result
5. Repeats until it has a complete answer
6. Returns FINAL_ANSWER
