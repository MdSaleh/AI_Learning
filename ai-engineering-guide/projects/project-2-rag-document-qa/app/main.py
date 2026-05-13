"""RAG Document Q&A API — main application."""
import uuid
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Annotated, AsyncGenerator, Optional

import chromadb
import structlog
from fastapi import (
    BackgroundTasks,
    Depends,
    FastAPI,
    File,
    HTTPException,
    Request,
    Response,
    UploadFile,
    status,
)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest
from pydantic import BaseModel, Field

from app.ingestion.pipeline import ingest_file
from app.services.rag import RAGService

logger = structlog.get_logger()

UPLOAD_DIR = Path("./data/uploads")
CHROMA_DIR = Path("./data/chroma")
ALLOWED_TYPES = {"application/pdf", "text/plain", "text/markdown"}
MAX_FILE_SIZE = 50 * 1_024 * 1_024  # 50 MB


# ─── Schemas ──────────────────────────────────────────────────────────────────
class AskRequest(BaseModel):
    question: str = Field(..., min_length=3, max_length=5000)
    top_k: int = Field(default=5, ge=1, le=20)
    min_similarity: float = Field(default=0.5, ge=0.0, le=1.0)
    doc_id: Optional[str] = Field(default=None, description="Restrict to one document")
    temperature: float = Field(default=0.1, ge=0.0, le=1.0)


class AskResponse(BaseModel):
    answer: str
    sources: list[str]
    chunks_used: int
    top_similarity: float
    retrieved_chunks: list[dict]
    latency_ms: float


class UploadResponse(BaseModel):
    doc_id: str
    filename: str
    size_bytes: int
    status: str
    message: str


class DocumentInfo(BaseModel):
    doc_id: str
    filename: str
    chunk_count: int


# ─── Lifespan ─────────────────────────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    CHROMA_DIR.mkdir(parents=True, exist_ok=True)

    chroma_client = chromadb.PersistentClient(path=str(CHROMA_DIR))
    collection = chroma_client.get_or_create_collection(
        name="documents",
        metadata={"hnsw:space": "cosine"},
    )
    app.state.collection = collection
    app.state.rag_service = RAGService(collection)

    doc_count = collection.count()
    logger.info("rag_service_ready", documents_in_db=doc_count)
    yield
    logger.info("shutting_down")


# ─── App ──────────────────────────────────────────────────────────────────────
app = FastAPI(
    title="RAG Document Q&A API",
    description="""
Upload documents (PDF, TXT, Markdown) and ask questions about them.
Uses local LLM via Ollama — **completely free, runs on your machine**.

## Workflow
1. **Upload** a document via `POST /documents/upload`
2. **Ask** a question via `POST /ask`
3. Get a **grounded answer** with source citations

## Setup
```bash
ollama pull llama3.1:8b
ollama pull nomic-embed-text
uvicorn app.main:app --reload
```
    """,
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


def get_rag(request: Request) -> RAGService:
    return request.app.state.rag_service


def get_collection(request: Request) -> chromadb.Collection:
    return request.app.state.collection


RAGDep = Annotated[RAGService, Depends(get_rag)]
CollectionDep = Annotated[chromadb.Collection, Depends(get_collection)]


# ─── Endpoints ────────────────────────────────────────────────────────────────

@app.post("/documents/upload", response_model=UploadResponse, tags=["Documents"])
async def upload_document(
    background_tasks: BackgroundTasks,
    collection: CollectionDep,
    file: UploadFile = File(...),
) -> UploadResponse:
    """
    Upload and ingest a document.
    Processing happens in the background — returns immediately.
    """
    if file.content_type not in ALLOWED_TYPES:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=f"File type '{file.content_type}' not supported. Use PDF, TXT, or Markdown.",
        )

    content = await file.read()
    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="File too large. Maximum 50MB.",
        )

    # Save file
    safe_name = Path(file.filename).name
    saved_path = UPLOAD_DIR / f"{uuid.uuid4()}_{safe_name}"
    saved_path.write_bytes(content)

    # Generate doc_id for the response
    import hashlib
    doc_id = hashlib.sha256(str(saved_path.resolve()).encode()).hexdigest()[:16]

    # Ingest in background (don't block response)
    background_tasks.add_task(ingest_file, saved_path, collection)

    logger.info("document_upload_queued", filename=file.filename, doc_id=doc_id, size=len(content))

    return UploadResponse(
        doc_id=doc_id,
        filename=file.filename,
        size_bytes=len(content),
        status="processing",
        message="Document is being ingested. It will be searchable in a few seconds.",
    )


@app.post("/ask", response_model=AskResponse, tags=["Q&A"])
async def ask_question(request: AskRequest, rag: RAGDep) -> AskResponse:
    """
    Ask a question about your uploaded documents.
    Returns a grounded answer with source citations.
    """
    logger.info("question_received", question=request.question[:100])

    result = await rag.answer(
        query=request.question,
        top_k=request.top_k,
        min_similarity=request.min_similarity,
        temperature=request.temperature,
        filter_doc_id=request.doc_id,
    )

    return AskResponse(**result)


@app.get("/documents", tags=["Documents"])
async def list_documents(collection: CollectionDep) -> dict:
    """List all ingested documents."""
    all_items = collection.get(include=["metadatas"])
    docs: dict[str, dict] = {}

    for meta in (all_items.get("metadatas") or []):
        doc_id = meta.get("doc_id", "unknown")
        if doc_id not in docs:
            docs[doc_id] = {
                "doc_id": doc_id,
                "filename": meta.get("filename", "unknown"),
                "chunk_count": 0,
                "file_type": meta.get("file_type", ""),
            }
        docs[doc_id]["chunk_count"] += 1

    return {
        "documents": list(docs.values()),
        "total_documents": len(docs),
        "total_chunks": collection.count(),
    }


@app.delete("/documents/{doc_id}", tags=["Documents"])
async def delete_document(doc_id: str, collection: CollectionDep) -> dict:
    """Delete a document and all its chunks from the vector store."""
    existing = collection.get(where={"doc_id": doc_id})
    if not existing["ids"]:
        raise HTTPException(status_code=404, detail=f"Document '{doc_id}' not found")

    collection.delete(ids=existing["ids"])
    logger.info("document_deleted", doc_id=doc_id, chunks_deleted=len(existing["ids"]))

    return {"doc_id": doc_id, "chunks_deleted": len(existing["ids"]), "status": "deleted"}


@app.get("/health", tags=["System"])
async def health(collection: CollectionDep) -> dict:
    return {
        "status": "healthy",
        "service": "RAG Document Q&A API",
        "documents_indexed": collection.count(),
    }


@app.get("/metrics", tags=["System"])
async def metrics() -> Response:
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)
