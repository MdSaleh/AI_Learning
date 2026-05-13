# 🧠 AI Fundamentals for Engineers
> The theory and intuition every AI engineer must understand

---

## 1. Large Language Models (LLMs) — What Actually Happens

### How LLMs Work (No PhD Required)

```
Your text → Tokenizer → Token IDs → Transformer → Probabilities → Next token → Repeat
```

**Tokens** — LLMs don't see words, they see tokens (sub-word chunks):
```python
# Example tokenization (conceptual — tiktoken uses this):
# "Hello, world!" → ["Hello", ",", " world", "!"] → [15496, 11, 995, 0]
# "AI engineering" → ["AI", " engineer", "ing"] → [15836, 10950, 278]

# Install: pip install tiktoken
import tiktoken

encoder = tiktoken.encoding_for_model("gpt-4")
text = "Build production AI systems with Python and FastAPI"
tokens = encoder.encode(text)
print(f"Tokens: {len(tokens)}")  # ~9 tokens
print(f"Token IDs: {tokens[:5]}")

# Rule of thumb: 1 token ≈ 4 characters, or ¾ of a word
# 1000 tokens ≈ 750 words ≈ 1-2 pages of text
```

**Context Window** — How much the model can "see" at once:
- Llama 3.1 8B: 128K tokens
- GPT-4o: 128K tokens  
- Claude 3.5: 200K tokens

**Temperature** — How random/creative the output is:
```
Temperature 0.0 → Always picks most likely token → Deterministic, factual
Temperature 0.7 → Balanced creativity → Good for chat
Temperature 1.5 → Very random → Creative writing, poetry
Temperature 2.0 → Nearly random → Usually garbage
```

**Top-P / Top-K** — Alternative sampling strategies:
```
Top-K=50   → Only consider top 50 most likely tokens
Top-P=0.9  → Consider tokens until cumulative probability reaches 90%
```

---

## 2. Embeddings — The Core of RAG

### What Are Embeddings?

Embeddings turn text into numbers (vectors) that **capture meaning**:
```
"I love dogs"  → [0.23, -0.45, 0.12, ..., 0.89]  # 768 numbers
"I adore dogs" → [0.24, -0.44, 0.13, ..., 0.87]  # Very similar!
"I hate math"  → [-0.34, 0.67, -0.23, ..., 0.11] # Very different
```

Similar meanings → similar vectors → high cosine similarity score.

### Computing Embeddings Locally (Free with Ollama)

```python
import httpx
import numpy as np
from typing import Union

async def get_embedding(text: str, model: str = "nomic-embed-text") -> list[float]:
    """Get embedding from local Ollama — completely free."""
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(
            "http://localhost:11434/api/embeddings",
            json={"model": model, "prompt": text}
        )
        return response.json()["embedding"]

def cosine_similarity(v1: list[float], v2: list[float]) -> float:
    """Measure how similar two embeddings are. Range: -1 to 1."""
    a, b = np.array(v1), np.array(v2)
    return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b)))

# Demonstration:
async def demo_semantic_search():
    query = "how to train a neural network"
    
    documents = [
        "Training neural networks requires data, optimizer, and loss function",
        "Python is a great programming language for beginners",
        "Backpropagation is the algorithm used to train deep learning models",
        "The capital of France is Paris",
        "Gradient descent minimizes the loss function during model training",
    ]
    
    query_emb = await get_embedding(query)
    doc_embs = [await get_embedding(doc) for doc in documents]
    
    # Rank by similarity
    similarities = [
        (cosine_similarity(query_emb, doc_emb), doc)
        for doc_emb, doc in zip(doc_embs, documents)
    ]
    similarities.sort(reverse=True)
    
    print(f"Query: {query}\n")
    print("Top results:")
    for score, doc in similarities[:3]:
        print(f"  [{score:.3f}] {doc}")

# Output:
# [0.921] Training neural networks requires data, optimizer, and loss function
# [0.894] Gradient descent minimizes the loss function during model training
# [0.871] Backpropagation is the algorithm used to train deep learning models
```

---

## 3. RAG — Retrieval Augmented Generation

### Why RAG? The Problem It Solves

```
Problem: LLMs have a knowledge cutoff. They don't know about:
  - Your company's internal documents
  - Last week's news
  - Your codebase
  - Your customer data

Solution: RAG = Give the LLM your documents at query time

Flow:
  User question 
    → embed question
    → search vector DB for similar documents  
    → inject top docs into LLM prompt
    → LLM answers using YOUR documents
    → Grounded, accurate answer
```

### RAG Pipeline — Step by Step

```python
# Complete RAG pipeline implementation

# ─── STEP 1: Ingestion (run once) ────────────────────────────────────────────
import chromadb
from pathlib import Path

async def ingest_documents(file_paths: list[Path]) -> None:
    """Convert documents to embeddings and store in vector DB."""
    client = chromadb.PersistentClient(path="./data/chroma")
    collection = client.get_or_create_collection(
        name="documents",
        metadata={"hnsw:space": "cosine"}
    )
    
    for filepath in file_paths:
        text = filepath.read_text(encoding="utf-8")
        chunks = split_into_chunks(text, chunk_size=500, overlap=50)
        
        for i, chunk in enumerate(chunks):
            embedding = await get_embedding(chunk)
            collection.add(
                ids=[f"{filepath.stem}_{i}"],
                embeddings=[embedding],
                documents=[chunk],
                metadatas=[{
                    "source": str(filepath),
                    "chunk_index": i,
                    "total_chunks": len(chunks)
                }]
            )
    
    print(f"✅ Ingested {collection.count()} chunks")

def split_into_chunks(
    text: str,
    chunk_size: int = 500,
    overlap: int = 50
) -> list[str]:
    """Split text into overlapping chunks."""
    # Clean text
    text = " ".join(text.split())
    
    chunks = []
    start = 0
    while start < len(text):
        end = start + chunk_size
        chunk = text[start:end]
        
        # Try to break at sentence boundary
        if end < len(text):
            last_period = chunk.rfind(". ")
            if last_period > chunk_size // 2:
                end = start + last_period + 1
                chunk = text[start:end]
        
        if chunk.strip():
            chunks.append(chunk.strip())
        start = end - overlap
    
    return chunks

# ─── STEP 2: Retrieval (run on every query) ───────────────────────────────────
async def retrieve_relevant_chunks(
    query: str,
    collection: chromadb.Collection,
    top_k: int = 5
) -> list[dict]:
    """Find the most relevant document chunks for a query."""
    query_embedding = await get_embedding(query)
    
    results = collection.query(
        query_embeddings=[query_embedding],
        n_results=top_k,
        include=["documents", "metadatas", "distances"]
    )
    
    chunks = []
    for doc, meta, dist in zip(
        results["documents"][0],
        results["metadatas"][0], 
        results["distances"][0]
    ):
        chunks.append({
            "text": doc,
            "source": meta.get("source", "unknown"),
            "similarity": 1 - dist,  # Convert distance to similarity
            "metadata": meta
        })
    
    return chunks

# ─── STEP 3: Generation (augmented with retrieved context) ────────────────────
async def answer_with_rag(query: str, collection: chromadb.Collection) -> dict:
    """Full RAG pipeline: retrieve + generate."""
    # Retrieve
    chunks = await retrieve_relevant_chunks(query, collection, top_k=5)
    
    # Filter by quality
    good_chunks = [c for c in chunks if c["similarity"] > 0.7]
    
    if not good_chunks:
        return {
            "answer": "I don't have relevant information to answer this question.",
            "sources": [],
            "chunks_used": 0
        }
    
    # Build context
    context = "\n\n---\n\n".join([
        f"Source: {c['source']}\n{c['text']}"
        for c in good_chunks
    ])
    
    # Create prompt
    prompt = f"""You are a helpful assistant. Answer the question using ONLY the provided context.
If the context doesn't contain enough information, say so clearly.
Do not make up information.

Context:
{context}

Question: {query}

Answer:"""
    
    # Generate
    answer = await generate_with_ollama(prompt)
    
    return {
        "answer": answer,
        "sources": list(set(c["source"] for c in good_chunks)),
        "chunks_used": len(good_chunks),
        "top_similarity": good_chunks[0]["similarity"]
    }

async def generate_with_ollama(prompt: str, model: str = "llama3.1:8b") -> str:
    """Generate text with local Ollama."""
    async with httpx.AsyncClient(timeout=120.0) as client:
        response = await client.post(
            "http://localhost:11434/api/generate",
            json={"model": model, "prompt": prompt, "stream": False}
        )
        return response.json()["response"]
```

---

## 4. AI Agents — LLMs That Take Actions

### What is an Agent?

```
Basic LLM: Question → Answer (single call, no tools)
Agent:      Question → Think → Use Tool → Think → Use Tool → ... → Final Answer
```

An agent can:
- Search the web
- Run code
- Query databases
- Call APIs
- Read/write files
- Send emails

### Agent Architecture

```
User Input
    ↓
[Agent LLM] ← System prompt with available tools
    ↓
Decides: "I need to search the web"
    ↓
[Tool Executor] → executes web_search("Python FastAPI tutorial")
    ↓
Tool Result → fed back to LLM
    ↓
[Agent LLM] → "Now I have enough info"
    ↓
Final Answer
```

### Simple ReAct Agent Pattern

```python
import json
from typing import Callable

# Define tools the agent can use
TOOLS = {
    "search_docs": {
        "description": "Search internal documents for information",
        "parameters": {"query": "string - what to search for"}
    },
    "calculate": {
        "description": "Perform mathematical calculations", 
        "parameters": {"expression": "string - math expression to evaluate"}
    },
    "get_current_time": {
        "description": "Get the current date and time",
        "parameters": {}
    }
}

async def react_agent(user_query: str, max_steps: int = 10) -> str:
    """
    ReAct (Reason + Act) agent pattern.
    Iterates: Think → Act → Observe → Think...
    """
    system_prompt = f"""You are a helpful AI assistant with access to tools.

Available tools:
{json.dumps(TOOLS, indent=2)}

To use a tool, respond with EXACTLY this format:
THINK: <your reasoning about what to do next>
ACTION: <tool_name>
INPUT: <json input for the tool>

When you have a final answer, respond with:
THINK: <final reasoning>
FINAL_ANSWER: <your complete answer to the user>

Always start with THINK."""

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_query}
    ]
    
    for step in range(max_steps):
        response = await call_llm(messages)
        messages.append({"role": "assistant", "content": response})
        
        if "FINAL_ANSWER:" in response:
            answer_start = response.index("FINAL_ANSWER:") + len("FINAL_ANSWER:")
            return response[answer_start:].strip()
        
        if "ACTION:" in response:
            tool_name = extract_between(response, "ACTION:", "INPUT:").strip()
            tool_input_str = extract_after(response, "INPUT:").strip()
            
            try:
                tool_input = json.loads(tool_input_str)
                tool_result = await execute_tool(tool_name, tool_input)
            except Exception as e:
                tool_result = f"Error executing tool: {e}"
            
            messages.append({
                "role": "user",
                "content": f"OBSERVATION: {tool_result}"
            })
    
    return "Agent reached maximum steps without completing the task."
```

---

## 5. Prompt Engineering — Making LLMs Do What You Want

### Core Techniques

```python
# ─── 1. System + User separation ─────────────────────────────────────────────
messages = [
    {
        "role": "system",
        "content": """You are an expert Python code reviewer.
        
Your job:
1. Identify bugs and security issues
2. Suggest performance improvements
3. Check for PEP 8 compliance
4. Rate code quality 1-10

Always respond in JSON format:
{
  "rating": <1-10>,
  "bugs": ["list of bugs"],
  "improvements": ["list of suggestions"],
  "security": ["list of security issues"]
}"""
    },
    {
        "role": "user",
        "content": f"Review this code:\n```python\n{code}\n```"
    }
]

# ─── 2. Few-shot examples ─────────────────────────────────────────────────────
few_shot_prompt = """Extract the main topic, sentiment, and key entities from text.

Example 1:
Text: "Apple's new iPhone 16 has great camera features but battery life is disappointing"
Output: {"topic": "iPhone 16 review", "sentiment": "mixed", "entities": ["Apple", "iPhone 16"]}

Example 2:  
Text: "Python 3.12 brings massive performance improvements to the language"
Output: {"topic": "Python release", "sentiment": "positive", "entities": ["Python 3.12"]}

Now analyze:
Text: "{user_text}"
Output:"""

# ─── 3. Chain of thought ──────────────────────────────────────────────────────
cot_prompt = """Solve this step by step.

Problem: {problem}

Think through this:
1. What do I know?
2. What approach should I use?
3. Work through the solution step by step
4. Double-check my answer

Solution:"""

# ─── 4. Structured output extraction ─────────────────────────────────────────
extraction_prompt = """Extract information from this job posting.

Job Posting:
{job_text}

Return a JSON object with exactly these fields:
- title: job title (string)
- company: company name (string)  
- salary_min: minimum salary in USD (integer or null if not mentioned)
- salary_max: maximum salary in USD (integer or null if not mentioned)
- required_skills: list of required skills (array of strings)
- remote: whether remote work is offered (boolean)
- experience_years: years of experience required (integer or null)

JSON:"""
```

---

## 6. Model Selection Guide

| Use Case | Recommended Model | Why |
|----------|------------------|-----|
| Local chat | `llama3.1:8b` via Ollama | Fast, free, private |
| Local code | `deepseek-coder:6.7b` via Ollama | Code-focused |
| Local embeddings | `nomic-embed-text` via Ollama | High quality, free |
| Fast cloud API | Groq + Llama3 (free tier) | 500 tokens/sec |
| Best quality | Groq + Mixtral (free tier) | Good quality, fast |
| Embeddings cloud | Free tier from Cohere | 1M free tokens/month |

**Always start local with Ollama. Go cloud only when needed.**

---

**Next Module**: [FastAPI →](../03-fastapi/README.md)
