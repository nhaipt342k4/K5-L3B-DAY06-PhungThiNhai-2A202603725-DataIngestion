"""Persistent vector store on Chroma (local, on disk), cosine distance.

Chosen instead of the pgvector starter because Docker is not available on the
author's machine; GUIDE.md allows Chroma. One collection per index.
"""
from typing import Any

import chromadb

from .models import Chunk


class ChromaStore:
    def __init__(self, path: str, dimensions: int) -> None:
        self.client = chromadb.PersistentClient(path=path)
        self.dimensions = dimensions

    def _collection(self, index: str):
        return self.client.get_or_create_collection(
            name=f"index_{index}",
            configuration={"hnsw": {"space": "cosine"}},
            embedding_function=None,
        )

    def count(self, index: str) -> int:
        return self._collection(index).count()

    def upsert(self, index: str, chunks: list[Chunk], vectors: list[list[float]]) -> dict[str, int]:
        """Write stable IDs (re-ingest = overwrite, no duplicates); delete obsolete chunks."""
        if len(chunks) != len(vectors):
            raise ValueError(f"{len(chunks)} chunks but {len(vectors)} vectors")
        if any(len(v) != self.dimensions for v in vectors):
            raise ValueError(f"vector dimension differs from {self.dimensions}")
        ids = [c.chunk_id for c in chunks]
        if len(set(ids)) != len(ids):
            raise ValueError("duplicate chunk_id in batch")
        col = self._collection(index)
        new_ids, removed = set(ids), 0
        for doc_id in {c.document_id for c in chunks}:
            old = col.get(where={"document_id": doc_id}, include=[])["ids"]
            obsolete = [i for i in old if i not in new_ids]
            if obsolete:
                col.delete(ids=obsolete)
                removed += len(obsolete)
        metadatas = [
            {k: v for k, v in {**c.metadata, "document_id": c.document_id,
                               "source": c.source, "page": c.page}.items() if v is not None}
            for c in chunks
        ]
        for start in range(0, len(ids), 500):
            end = start + 500
            col.upsert(ids=ids[start:end], embeddings=vectors[start:end],
                       documents=[c.text for c in chunks[start:end]], metadatas=metadatas[start:end])
        return {"upserted": len(ids), "removed_obsolete": removed, "count_after": col.count()}

    @staticmethod
    def _where(filters: dict[str, Any] | None) -> dict | None:
        if not filters:
            return None
        clauses = [{k: v} for k, v in filters.items()]
        return clauses[0] if len(clauses) == 1 else {"$and": clauses}

    def search(self, index: str, query_vector: list[float], top_k: int = 3,
               filters: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        """Metadata filter applied inside Chroma; rank by cosine; return top-k."""
        res = self._collection(index).query(
            query_embeddings=[query_vector], n_results=top_k, where=self._where(filters),
            include=["documents", "metadatas", "distances"],
        )
        return [
            {"rank": r + 1, "chunk_id": cid, "score": round(1 - dist, 4),
             "page": meta.get("page"), "source": meta.get("source"), "metadata": meta, "text": doc}
            for r, (cid, doc, meta, dist) in enumerate(zip(
                res["ids"][0], res["documents"][0], res["metadatas"][0], res["distances"][0]))
        ]
