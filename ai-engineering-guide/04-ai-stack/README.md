# 🤖 AI Stack — LangChain, Ollama, ChromaDB, Agents
> The complete open-source AI toolkit — all free, all local

---

## 1. Ollama — Run LLMs Locally (FREE)

```bash
# Install
curl -fsSL https://ollama.ai/install.sh | sh

# Start server (runs on http://localhost:11434)
ollama serve

# Pull models (pick based on your RAM)
ollama pull llama3.1:8b         # 8B params — needs 8GB RAM — RECOMMENDED
ollama pull llama3.1:70b        # 70B params — needs 64GB RAM — Best quality
ollama pull deepseek-coder:6.7b # Code-focused — great for coding tasks
ollama pull mistral:7b          # Fast, multilingual
ollama pull phi3:mini           # Tiny but smart — 4GB RAM
ollama pull nomic-embed-text    # Embeddings — ALWAYS pull this one

# List installed models
ollama list

# Remove a model
ollama rm llama3.1:8b

# Test in terminal
ollama run llama3.1:8b "Explain machine learning in 2 sentences"

# API calls (Ollama has an OpenAI-compatible API)
curl http://localhost:11434/api/generate \
  -d '{"model": "llama3.1:8b", "prompt": "Hello!", "stream": false}'

# OpenAI-compatible endpoint (drop-in replacement!)
curl http://localhost:11434/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "llama3.1:8b",
    "messages": [{"role": "user", "content": "Hello!"}]
  }'
```

### Using Ollama in Python:
```python
from openai import AsyncOpenAI  # pip install openai

# Point to local Ollama — same API as OpenAI!
client = AsyncOpenAI(
    base_url="http://localhost:11434/v1",
    api_key="ollama",  # Required but ignored by Ollama
)

async def chat(message: str) -> str:
    response = await client.chat.completions.create(
        model="llama3.1:8b",
        messages=[{"role": "user", "content": message}],
        temperature=0.7,
    )
    return response.choices[0].message.content

async def stream_chat(message: str):
    stream = await client.chat.completions.create(
        model="llama3.1:8b",
        messages=[{"role": "user", "content": message}],
        stream=True,
    )
    async for chunk in stream:
        if chunk.choices[0].delta.content:
            yield chunk.choices[0].delta.content
```

---

## 2. Groq — Free Cloud LLM API (Blazing Fast)

Get free API key: https://console.groq.com (no credit card needed!)

```python
from openai import AsyncOpenAI

# Groq uses OpenAI-compatible API — same code, different URL!
groq_client = AsyncOpenAI(
    base_url="https://api.groq.com/openai/v1",
    api_key="your-groq-api-key",  # Free at console.groq.com
)

# Available free models on Groq:
# - llama3-70b-8192     (best quality, 70B params)
# - llama3-8b-8192      (fast, 8B params)
# - mixtral-8x7b-32768  (great for analysis, 32K context)
# - gemma-7b-it         (Google's Gemma)

async def fast_chat(message: str) -> str:
    """500+ tokens/sec — 10x faster than most APIs!"""
    response = await groq_client.chat.completions.create(
        model="llama3-70b-8192",
        messages=[{"role": "user", "content": message}],
    )
    return response.choices[0].message.content

# Free tier limits (as of 2024):
# 30 requests/minute, 14,400 requests/day
# 6,000 tokens/minute
```

---

## 3. ChromaDB — Free Vector Database

```python
import chromadb
from chromadb.config import Settings

# ─── Persistent (saves to disk) ───────────────────────────────────────────────
client = chromadb.PersistentClient(
    path="./data/chroma",
    settings=Settings(anonymized_telemetry=False)
)

# ─── In-memory (for testing) ───────────────────────────────────────────────────
client = chromadb.Client()

# ─── Create/Get collection ────────────────────────────────────────────────────
collection = client.get_or_create_collection(
    name="my_documents",
    metadata={"hnsw:space": "cosine"},  # Use cosine similarity
)

# ─── Add documents ────────────────────────────────────────────────────────────
collection.add(
    ids=["doc1", "doc2", "doc3"],
    documents=[
        "Machine learning uses data to make predictions",
        "Neural networks are inspired by the human brain",
        "Python is the most popular language for AI",
    ],
    embeddings=[
        [0.1, 0.2, 0.3, ...],  # Pre-computed embeddings
        [0.4, 0.5, 0.6, ...],
        [0.7, 0.8, 0.9, ...],
    ],
    metadatas=[
        {"source": "textbook", "chapter": 1},
        {"source": "paper", "year": 2023},
        {"source": "blog", "author": "Alice"},
    ],
)

# ─── Query ────────────────────────────────────────────────────────────────────
results = collection.query(
    query_embeddings=[[0.15, 0.25, 0.35, ...]],  # Your query embedding
    n_results=3,
    include=["documents", "metadatas", "distances"],
    where={"source": "textbook"},          # Filter by metadata
    where_document={"$contains": "learn"}, # Filter by text content
)

print(results["documents"])   # Most similar docs
print(results["distances"])   # Lower = more similar (L2/cosine)

# ─── Update documents ─────────────────────────────────────────────────────────
collection.update(
    ids=["doc1"],
    documents=["Updated: Machine learning is amazing"],
    metadatas=[{"source": "textbook", "chapter": 1, "updated": True}],
)

# ─── Delete ───────────────────────────────────────────────────────────────────
collection.delete(ids=["doc1"])
collection.delete(where={"source": "old_source"})

# ─── Collection stats ─────────────────────────────────────────────────────────
print(f"Documents in collection: {collection.count()}")
all_docs = collection.get()  # Get everything
```

---

## 4. Sentence Transformers — Free Embeddings (No API Needed)

```python
from sentence_transformers import SentenceTransformer
import numpy as np

# ─── Load model (downloads once, then cached) ─────────────────────────────────
# Best free models:
model = SentenceTransformer("all-MiniLM-L6-v2")      # 384 dims, fast
model = SentenceTransformer("all-mpnet-base-v2")      # 768 dims, better quality
model = SentenceTransformer("BAAI/bge-small-en-v1.5") # Best for RAG

# ─── Single embedding ─────────────────────────────────────────────────────────
text = "Machine learning is transforming the world"
embedding = model.encode(text)  # Returns numpy array
print(f"Embedding shape: {embedding.shape}")  # (384,) or (768,)

# ─── Batch embedding (much faster than one-by-one) ───────────────────────────
texts = [
    "First document about AI",
    "Second document about Python",
    "Third document about databases",
]
embeddings = model.encode(texts, batch_size=32, show_progress_bar=True)
print(f"Batch shape: {embeddings.shape}")  # (3, 384)

# ─── Semantic similarity ──────────────────────────────────────────────────────
from sentence_transformers import util

query = "How does machine learning work?"
docs = ["ML uses algorithms to learn from data", "Paris is in France"]

query_emb = model.encode(query)
doc_embs = model.encode(docs)

# Cosine similarity
scores = util.cos_sim(query_emb, doc_embs)
print(f"Similarities: {scores}")  # [[0.87, 0.12]]

# Find most similar
top_k = util.semantic_search(query_emb, doc_embs, top_k=1)
print(f"Best match: {docs[top_k[0][0]['corpus_id']]}")
```

---

## 5. LangChain Essentials

```python
# pip install langchain langchain-community langchain-ollama

from langchain_ollama import ChatOllama
from langchain_core.messages import HumanMessage, SystemMessage, AIMessage
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate

# ─── Basic LLM call ───────────────────────────────────────────────────────────
llm = ChatOllama(model="llama3.1:8b", temperature=0.7)

messages = [
    SystemMessage(content="You are a helpful Python tutor."),
    HumanMessage(content="Explain list comprehensions"),
]
response = llm.invoke(messages)
print(response.content)

# ─── LCEL (LangChain Expression Language) — Pipe chains ──────────────────────
prompt = ChatPromptTemplate.from_messages([
    ("system", "You are a {role}. Answer concisely."),
    ("human", "{question}")
])

chain = prompt | llm | StrOutputParser()

result = chain.invoke({
    "role": "Python expert",
    "question": "What is a decorator?"
})
print(result)

# ─── Streaming ────────────────────────────────────────────────────────────────
for chunk in chain.stream({"role": "teacher", "question": "Explain async/await"}):
    print(chunk, end="", flush=True)

# ─── RAG chain ────────────────────────────────────────────────────────────────
from langchain_chroma import Chroma
from langchain_ollama import OllamaEmbeddings
from langchain_core.runnables import RunnablePassthrough

embeddings = OllamaEmbeddings(model="nomic-embed-text")
vectorstore = Chroma(persist_directory="./data/chroma", embedding_function=embeddings)
retriever = vectorstore.as_retriever(search_kwargs={"k": 5})

rag_prompt = ChatPromptTemplate.from_template("""
Answer based ONLY on this context:
{context}

Question: {question}
Answer:""")

rag_chain = (
    {"context": retriever, "question": RunnablePassthrough()}
    | rag_prompt
    | llm
    | StrOutputParser()
)

answer = rag_chain.invoke("What is machine learning?")
```

---

## 6. Model Selection Decision Tree

```
Do you need internet search results? → Use web_search tool in agent
Do you need free & private? → Ollama (local)
Do you need fastest possible? → Groq API (free tier)
Do you need best quality? → Groq + llama3-70b
Do you need embeddings? → nomic-embed-text (Ollama) or all-MiniLM-L6-v2
Do you need to run on cheap hardware? → phi3:mini via Ollama (4GB RAM)
```

---

## Quick Install — Everything at Once

```bash
pip install \
  langchain langchain-community langchain-ollama langchain-chroma \
  chromadb \
  sentence-transformers \
  openai \
  httpx
```
