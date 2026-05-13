"""RAG service — retrieval-augmented generation for document Q&A."""
import time
from typing import Optional

import chromadb
import httpx
import structlog
from prometheus_client import Counter, Histogram

logger = structlog.get_logger()

# ─── Metrics ─────────────────────────────────────────────────────────────────
RAG_QUERIES = Counter("rag_queries_total", "Total RAG queries", ["status"])
RAG_LATENCY = Histogram(
    "rag_latency_seconds",
    "End-to-end RAG latency",
    buckets=[0.1, 0.5, 1.0, 2.0, 5.0, 10.0, 30.0],
)
RETRIEVAL_LATENCY = Histogram(
    "rag_retrieval_latency_seconds",
    "Vector search latency",
    buckets=[0.001, 0.01, 0.05, 0.1, 0.5],
)
CHUNKS_RETRIEVED = Histogram(
    "rag_chunks_retrieved",
    "Number of chunks retrieved per query",
    buckets=[1, 2, 3, 4, 5, 7, 10],
)


class RAGService:
    """
    Retrieval-Augmented Generation service.
    Answers questions using your document collection.
    """

    def __init__(
        self,
        collection: chromadb.Collection,
        ollama_url: str = "http://localhost:11434",
        embedding_model: str = "nomic-embed-text",
        llm_model: str = "llama3.1:8b",
    ) -> None:
        self.collection = collection
        self.ollama_url = ollama_url
        self.embedding_model = embedding_model
        self.llm_model = llm_model

    async def get_query_embedding(self, query: str) -> list[float]:
        """Embed the user query."""
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"{self.ollama_url}/api/embeddings",
                json={"model": self.embedding_model, "prompt": query},
            )
            response.raise_for_status()
            return response.json()["embedding"]

    async def retrieve(
        self,
        query: str,
        top_k: int = 5,
        min_similarity: float = 0.5,
        filter_doc_id: Optional[str] = None,
    ) -> list[dict]:
        """
        Retrieve the most relevant document chunks for a query.

        Args:
            query: The user's question
            top_k: Number of chunks to retrieve
            min_similarity: Minimum cosine similarity threshold (0-1)
            filter_doc_id: Optional — restrict search to one document

        Returns:
            List of chunks with text, source, and similarity score
        """
        start = time.perf_counter()

        # Embed query
        query_embedding = await self.get_query_embedding(query)

        # Build ChromaDB query
        where = {"doc_id": filter_doc_id} if filter_doc_id else None

        results = self.collection.query(
            query_embeddings=[query_embedding],
            n_results=min(top_k, self.collection.count() or 1),
            include=["documents", "metadatas", "distances"],
            where=where,
        )

        retrieval_time = time.perf_counter() - start
        RETRIEVAL_LATENCY.observe(retrieval_time)

        # Parse and filter results
        chunks = []
        if results["documents"] and results["documents"][0]:
            for doc, meta, dist in zip(
                results["documents"][0],
                results["metadatas"][0],
                results["distances"][0],
            ):
                # ChromaDB returns L2 distance for cosine space — convert
                similarity = 1 - dist  # Higher = more similar
                if similarity >= min_similarity:
                    chunks.append({
                        "text": doc,
                        "source": meta.get("filename", "unknown"),
                        "doc_id": meta.get("doc_id", ""),
                        "chunk_index": meta.get("chunk_index", 0),
                        "similarity": round(similarity, 4),
                        "metadata": meta,
                    })

        CHUNKS_RETRIEVED.observe(len(chunks))
        logger.info(
            "retrieval_complete",
            query_length=len(query),
            chunks_found=len(chunks),
            retrieval_ms=round(retrieval_time * 1000, 2),
        )
        return chunks

    async def answer(
        self,
        query: str,
        top_k: int = 5,
        min_similarity: float = 0.5,
        temperature: float = 0.1,  # Low temp for factual answers
        filter_doc_id: Optional[str] = None,
    ) -> dict:
        """
        Full RAG pipeline: retrieve relevant chunks → generate answer.

        Returns:
            dict with answer, sources, chunks used, and timing
        """
        start = time.perf_counter()

        # 1. Retrieve
        chunks = await self.retrieve(
            query,
            top_k=top_k,
            min_similarity=min_similarity,
            filter_doc_id=filter_doc_id,
        )

        if not chunks:
            RAG_QUERIES.labels(status="no_context").inc()
            return {
                "answer": (
                    "I couldn't find relevant information in the documents to answer your question. "
                    "Try rephrasing or uploading more relevant documents."
                ),
                "sources": [],
                "chunks_used": 0,
                "top_similarity": 0.0,
                "latency_ms": round((time.perf_counter() - start) * 1000, 2),
            }

        # 2. Build prompt with context
        context_parts = []
        for i, chunk in enumerate(chunks, 1):
            context_parts.append(
                f"[Source {i}: {chunk['source']} (similarity: {chunk['similarity']})]"
                f"\n{chunk['text']}"
            )
        context = "\n\n---\n\n".join(context_parts)

        prompt = f"""You are a precise document assistant. Answer the question using ONLY the provided context.

Rules:
- Answer only from the context provided
- If the context doesn't have enough information, say: "The documents don't contain enough information to answer this."
- Cite which source(s) you're drawing from (e.g., "According to [Source 1]...")
- Be concise and accurate
- Never make up information

Context:
{context}

Question: {query}

Answer:"""

        # 3. Generate
        answer_text = await self._generate(prompt, temperature=temperature)

        total_latency = time.perf_counter() - start
        RAG_LATENCY.observe(total_latency)
        RAG_QUERIES.labels(status="success").inc()

        sources = list({c["source"] for c in chunks})

        logger.info(
            "rag_answer_generated",
            query_length=len(query),
            chunks_used=len(chunks),
            sources=sources,
            latency_ms=round(total_latency * 1000, 2),
        )

        return {
            "answer": answer_text,
            "sources": sources,
            "chunks_used": len(chunks),
            "top_similarity": chunks[0]["similarity"] if chunks else 0.0,
            "retrieved_chunks": [
                {"text": c["text"][:200] + "...", "source": c["source"], "similarity": c["similarity"]}
                for c in chunks
            ],
            "latency_ms": round(total_latency * 1000, 2),
        }

    async def _generate(self, prompt: str, temperature: float = 0.1) -> str:
        """Call the LLM to generate a response."""
        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.post(
                f"{self.ollama_url}/api/generate",
                json={
                    "model": self.llm_model,
                    "prompt": prompt,
                    "stream": False,
                    "options": {"temperature": temperature},
                },
            )
            response.raise_for_status()
            return response.json()["response"]
