"""RAG module: ChromaDB for persistent vector storage, query-only from disk.

Only the SentenceTransformer embedder is cached in memory (needed for every query).
ChromaDB collection stays on disk — each query fetches only top-k results.

Build index:  python -m src.rag build
Query:        python -m src.rag query "FD minimum duration"
"""
from __future__ import annotations

import glob
import logging
import sys
from functools import lru_cache

import chromadb
from sentence_transformers import SentenceTransformer

from src.config import settings

logger = logging.getLogger(__name__)

COLLECTION_NAME = "banking_docs"


# ── Build ─────────────────────────────────────────────────────────────────────

def build_index() -> None:
    """Embed all markdown docs and store in ChromaDB collection."""
    embedder = SentenceTransformer(settings.rag_model)
    client = chromadb.PersistentClient(path=settings.rag_db_path)

    # Delete collection if it exists to rebuild from scratch
    try:
        client.delete_collection(name=COLLECTION_NAME)
    except Exception:
        pass

    collection = client.get_or_create_collection(
        name=COLLECTION_NAME,
        metadata={"hnsw:space": "cosine"},
    )

    chunks: list[str] = []
    sources: list[str] = []
    ids: list[str] = []

    doc_files = sorted(glob.glob(settings.rag_docs_glob))
    if not doc_files:
        raise RuntimeError(f"No documents found at {settings.rag_docs_glob}")

    chunk_id = 0
    for path in doc_files:
        text = open(path, encoding="utf-8").read()
        for para in [p.strip() for p in text.split("\n\n") if p.strip()]:
            chunks.append(para)
            sources.append(path)
            ids.append(str(chunk_id))
            chunk_id += 1

    print(f"Indexing {len(chunks)} chunks from {len(doc_files)} docs…")

    # Embed in batches (ChromaDB has batch limits)
    batch_size = 128
    for i in range(0, len(chunks), batch_size):
        batch_end = min(i + batch_size, len(chunks))
        batch_chunks = chunks[i:batch_end]
        batch_ids = ids[i:batch_end]
        batch_sources = sources[i:batch_end]

        embeddings = embedder.encode(
            ["passage: " + c for c in batch_chunks],
            normalize_embeddings=True,
            show_progress_bar=False,
        )

        collection.add(
            ids=batch_ids,
            embeddings=embeddings.tolist(),
            documents=batch_chunks,
            metadatas=[{"source": s} for s in batch_sources],
        )

    print(f"Saved {len(chunks)} vectors to {settings.rag_db_path}/{COLLECTION_NAME}")


# ── Query (only embedder cached; collection fetched from disk) ─────────────────

@lru_cache(maxsize=1)
def _get_embedder():
    """Cache only the embedder (needs to be in memory for every query)."""
    return SentenceTransformer(settings.rag_model)


def retrieve(query: str, k: int | None = None) -> list[dict]:
    """Return top-k relevant chunks. Each: {text, source, score}.

    ChromaDB collection stays on disk — only top-k results are fetched per query.
    """
    k = k or settings.rag_top_k

    # Create fresh client & get collection (lightweight, no data loaded)
    client = chromadb.PersistentClient(path=settings.rag_db_path)
    try:
        collection = client.get_collection(name=COLLECTION_NAME)
    except Exception:
        raise FileNotFoundError(
            f"ChromaDB collection '{COLLECTION_NAME}' not found at {settings.rag_db_path} — "
            "run `python -m src.rag build` first"
        )

    # Only embedder is cached (needed for embedding query text)
    embedder = _get_embedder()

    # Embed query
    qv = embedder.encode(
        ["query: " + query],
        normalize_embeddings=True,
    )

    # Query ChromaDB — fetches only top-k from disk (efficient)
    results = collection.query(
        query_embeddings=qv.tolist(),
        n_results=k,
    )

    # Format results
    hits = []
    if results["documents"] and len(results["documents"]) > 0:
        for i, doc in enumerate(results["documents"][0]):
            source = results["metadatas"][0][i]["source"]
            # ChromaDB returns distances (lower = better for cosine), convert to similarity
            distance = results["distances"][0][i] if results["distances"] else 0
            similarity = 1 - distance / 2  # Normalize cosine distance to [0, 1]
            hits.append({
                "text": doc,
                "source": source,
                "score": float(similarity),
            })

    return hits


# ── CLI ───────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    cmd = sys.argv[1] if len(sys.argv) > 1 else "query"
    if cmd == "build":
        build_index()
    else:
        q = " ".join(sys.argv[2:]) or "FD minimum duration kya hai?"
        for hit in retrieve(q):
            print(f"[{hit['score']:.3f}] {hit['source']}\n{hit['text'][:200]}\n")
