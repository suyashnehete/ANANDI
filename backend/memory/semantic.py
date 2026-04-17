"""
Semantic Memory — What ANANDI knows. Facts, preferences, and knowledge
extracted from all interactions.

Storage: ChromaDB (fact embeddings) + knowledge graph (entities via relational.py)
"""

from datetime import datetime


class SemanticMemory:
    """Manages semantic facts in ChromaDB's semantic_facts collection."""

    COLLECTION = "semantic_facts"

    def __init__(self, chroma_client, embedding_service):
        self._client = chroma_client
        self._embeddings = embedding_service
        self._collection = self._client.get_or_create_collection(
            name=self.COLLECTION,
            metadata={"hnsw:space": "cosine"},
        )

    def store(self, fact: str, metadata: dict | None = None):
        """Store a semantic fact or preference."""
        meta = metadata or {}
        meta.setdefault("timestamp", datetime.now().isoformat())
        meta.setdefault("type", "fact")
        doc_id = f"sem_{meta['timestamp']}_{self._collection.count()}"
        embedding = self._embeddings.embed(fact)

        # Check for contradicting facts — update if found
        existing = self.search(fact, n_results=1)
        if existing and existing[0]["relevance"] > 0.92:
            # Very similar fact exists — update it
            old_id = existing[0].get("id")
            if old_id:
                try:
                    self._collection.delete(ids=[old_id])
                except Exception:
                    pass

        self._collection.add(
            ids=[doc_id],
            documents=[fact],
            embeddings=[embedding],
            metadatas=[meta],
        )

    def search(self, query: str, n_results: int = 5, where: dict | None = None) -> list[dict]:
        """Semantic search over stored facts."""
        if self._collection.count() == 0:
            return []
        query_embedding = self._embeddings.embed(query)
        kwargs = {
            "query_embeddings": [query_embedding],
            "n_results": min(max(n_results, 1), 20),
        }
        if where:
            kwargs["where"] = where
        results = self._collection.query(**kwargs)
        facts = []
        if results and results.get("documents"):
            docs = results["documents"][0]
            metas = results["metadatas"][0] if results.get("metadatas") else [{}] * len(docs)
            dists = results["distances"][0] if results.get("distances") else [0.0] * len(docs)
            ids = results["ids"][0] if results.get("ids") else [""] * len(docs)
            for doc, meta, dist, doc_id in zip(docs, metas, dists, ids):
                facts.append({
                    "text": doc,
                    "metadata": meta,
                    "relevance": 1.0 - dist,
                    "id": doc_id,
                })
        return facts

    def forget(self, fact_query: str, threshold: float = 0.9):
        """Remove facts matching the query above the similarity threshold."""
        matches = self.search(fact_query, n_results=5)
        removed = 0
        for m in matches:
            if m["relevance"] >= threshold and m.get("id"):
                try:
                    self._collection.delete(ids=[m["id"]])
                    removed += 1
                except Exception:
                    pass
        return removed

    def count(self) -> int:
        return self._collection.count()
