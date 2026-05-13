# 📄 Project 2: RAG Document Q&A System

## What You'll Build
- Upload PDF/TXT/Markdown documents
- Ask questions — get grounded, cited answers
- Local LLM + local embeddings (completely free)
- ChromaDB vector store (persistent)
- Background ingestion (non-blocking uploads)

## Run It
```bash
# 1. Start Ollama
ollama serve
ollama pull llama3.1:8b
ollama pull nomic-embed-text

# 2. Install and run
python -m venv .venv && source .venv/bin/activate
pip install uv && uv pip install -e ".[dev]"
uvicorn app.main:app --reload --port 8001

# 3. Upload a document
curl -X POST http://localhost:8001/documents/upload \
  -F "file=@your-document.pdf"

# 4. Ask a question
curl -X POST http://localhost:8001/ask \
  -H "Content-Type: application/json" \
  -d '{"question": "What is this document about?"}'
```

## Architecture
User → FastAPI → ChromaDB (retrieve) → Ollama (generate) → Grounded Answer
