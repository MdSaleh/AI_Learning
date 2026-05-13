"""
Document ingestion pipeline — converts files to vector embeddings.
Supports: PDF, TXT, Markdown
"""
import hashlib
import re
from pathlib import Path
from typing import Iterator

import chromadb
import httpx
import structlog

logger = structlog.get_logger()


# ─── Text Extraction ──────────────────────────────────────────────────────────

def extract_text_from_txt(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def extract_text_from_pdf(path: Path) -> str:
    """Extract text from PDF using pypdf (free, no API needed)."""
    try:
        import pypdf
        reader = pypdf.PdfReader(str(path))
        pages = []
        for page in reader.pages:
            text = page.extract_text()
            if text:
                pages.append(text)
        return "\n\n".join(pages)
    except ImportError:
        raise RuntimeError("Install pypdf: pip install pypdf")
    except Exception as e:
        raise RuntimeError(f"PDF extraction failed: {e}")


def extract_text(path: Path) -> str:
    """Extract text from any supported file type."""
    suffix = path.suffix.lower()
    if suffix == ".pdf":
        return extract_text_from_pdf(path)
    elif suffix in (".txt", ".md", ".markdown", ".rst"):
        return extract_text_from_txt(path)
    else:
        raise ValueError(f"Unsupported file type: {suffix}")


# ─── Text Chunking ────────────────────────────────────────────────────────────

def clean_text(text: str) -> str:
    """Normalize whitespace and remove junk characters."""
    text = re.sub(r"\s+", " ", text)           # Collapse whitespace
    text = re.sub(r"[^\x20-\x7E\n]", "", text) # Remove non-printable chars
    text = re.sub(r"\n{3,}", "\n\n", text)      # Max 2 newlines
    return text.strip()


def chunk_text(
    text: str,
    chunk_size: int = 600,
    overlap: int = 100,
) -> list[str]:
    """
    Split text into overlapping chunks.
    Tries to break at sentence boundaries for better semantic coherence.
    """
    text = clean_text(text)
    if len(text) <= chunk_size:
        return [text] if text.strip() else []

    chunks = []
    start = 0

    while start < len(text):
        end = min(start + chunk_size, len(text))
        chunk = text[start:end]

        # Try to end at a sentence boundary (. ! ?)
        if end < len(text):
            for boundary in [". ", "! ", "? ", "\n\n", "\n"]:
                idx = chunk.rfind(boundary)
                if idx > chunk_size // 2:
                    chunk = chunk[:idx + len(boundary)]
                    end = start + len(chunk)
                    break

        if chunk.strip():
            chunks.append(chunk.strip())

        start = end - overlap
        if start >= len(text):
            break

    return chunks


# ─── Embeddings ───────────────────────────────────────────────────────────────

async def get_embedding(
    text: str,
    model: str = "nomic-embed-text",
    ollama_url: str = "http://localhost:11434",
) -> list[float]:
    """Get text embedding from local Ollama."""
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(
            f"{ollama_url}/api/embeddings",
            json={"model": model, "prompt": text},
        )
        response.raise_for_status()
        return response.json()["embedding"]


async def get_embeddings_batch(
    texts: list[str],
    model: str = "nomic-embed-text",
    ollama_url: str = "http://localhost:11434",
    batch_size: int = 10,
) -> list[list[float]]:
    """Get embeddings for a list of texts in batches."""
    import asyncio

    all_embeddings = []

    for i in range(0, len(texts), batch_size):
        batch = texts[i: i + batch_size]
        tasks = [get_embedding(t, model, ollama_url) for t in batch]
        embeddings = await asyncio.gather(*tasks, return_exceptions=True)

        for j, emb in enumerate(embeddings):
            if isinstance(emb, Exception):
                logger.error("embedding_failed", text_idx=i + j, error=str(emb))
                all_embeddings.append([])
            else:
                all_embeddings.append(emb)

        logger.info("batch_embedded", batch=i // batch_size + 1, total=len(texts))

    return all_embeddings


# ─── Ingestion Pipeline ────────────────────────────────────────────────────────

def doc_id_from_path(path: Path) -> str:
    """Generate stable doc ID from file path."""
    return hashlib.sha256(str(path.resolve()).encode()).hexdigest()[:16]


async def ingest_file(
    filepath: Path,
    collection: chromadb.Collection,
    embedding_model: str = "nomic-embed-text",
    ollama_url: str = "http://localhost:11434",
    chunk_size: int = 600,
    overlap: int = 100,
) -> dict:
    """
    Full ingestion pipeline for a single file.

    1. Extract text
    2. Chunk text
    3. Embed each chunk
    4. Store in ChromaDB

    Returns ingestion stats.
    """
    doc_id = doc_id_from_path(filepath)
    log = logger.bind(doc_id=doc_id, filename=filepath.name)

    log.info("ingestion_started")

    # 1. Extract text
    try:
        raw_text = extract_text(filepath)
    except Exception as e:
        log.error("text_extraction_failed", error=str(e))
        return {"doc_id": doc_id, "status": "failed", "error": str(e)}

    if not raw_text.strip():
        log.warning("empty_document")
        return {"doc_id": doc_id, "status": "skipped", "reason": "empty document"}

    # 2. Chunk
    chunks = chunk_text(raw_text, chunk_size=chunk_size, overlap=overlap)
    log.info("text_chunked", chunk_count=len(chunks))

    if not chunks:
        return {"doc_id": doc_id, "status": "skipped", "reason": "no chunks produced"}

    # 3. Embed
    embeddings = await get_embeddings_batch(chunks, model=embedding_model, ollama_url=ollama_url)

    # 4. Store in ChromaDB (delete old version first)
    existing = collection.get(where={"doc_id": doc_id})
    if existing["ids"]:
        collection.delete(ids=existing["ids"])
        log.info("old_version_deleted", count=len(existing["ids"]))

    # Build IDs and metadata
    ids = [f"{doc_id}_chunk_{i}" for i in range(len(chunks))]
    metadatas = [
        {
            "doc_id": doc_id,
            "filename": filepath.name,
            "filepath": str(filepath),
            "chunk_index": i,
            "total_chunks": len(chunks),
            "file_type": filepath.suffix.lower(),
        }
        for i in range(len(chunks))
    ]

    # Filter out failed embeddings
    valid = [
        (id_, emb, chunk, meta)
        for id_, emb, chunk, meta in zip(ids, embeddings, chunks, metadatas)
        if emb  # Skip empty embeddings from failures
    ]

    if not valid:
        return {"doc_id": doc_id, "status": "failed", "error": "all embeddings failed"}

    v_ids, v_embs, v_docs, v_metas = zip(*valid)

    collection.add(
        ids=list(v_ids),
        embeddings=list(v_embs),
        documents=list(v_docs),
        metadatas=list(v_metas),
    )

    log.info(
        "ingestion_complete",
        chunks_stored=len(valid),
        total_chars=len(raw_text),
    )

    return {
        "doc_id": doc_id,
        "filename": filepath.name,
        "status": "success",
        "chunks_stored": len(valid),
        "total_chars": len(raw_text),
    }


async def ingest_directory(
    directory: Path,
    collection: chromadb.Collection,
    patterns: list[str] = ("*.pdf", "*.txt", "*.md"),
) -> list[dict]:
    """Ingest all matching files from a directory."""
    files = []
    for pattern in patterns:
        files.extend(directory.glob(pattern))

    results = []
    for filepath in files:
        result = await ingest_file(filepath, collection)
        results.append(result)

    successful = sum(1 for r in results if r.get("status") == "success")
    logger.info("directory_ingestion_complete", total=len(files), successful=successful)
    return results
